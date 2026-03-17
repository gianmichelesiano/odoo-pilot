# src/odoo_pilot/odoo_writer.py
from __future__ import annotations

import logging
import xmlrpc.client

from odoo_pilot.config import Settings
from odoo_pilot.models import BusinessData, BusinessHours, ContactInfo, MenuItem

logger = logging.getLogger(__name__)


class OdooWriter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.uid: int | None = None
        self._common: xmlrpc.client.ServerProxy | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    def authenticate(self) -> None:
        """Authenticate to Odoo via XML-RPC."""
        url = self.settings.odoo_url.rstrip("/")
        self._common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self._models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

        self.uid = self._common.authenticate(
            self.settings.odoo_db,
            self.settings.odoo_user,
            self.settings.odoo_password,
            {},
        )

        if not self.uid:
            raise RuntimeError("Odoo authentication failed")

        logger.info(f"Authenticated to Odoo as uid={self.uid}")

    def _execute(self, model: str, method: str, *args, **kwargs):
        """Wrapper around execute_kw."""
        return self._models.execute_kw(
            self.settings.odoo_db,
            self.uid,
            self.settings.odoo_password,
            model,
            method,
            list(args),
            kwargs,
        )

    def _create_contact(self, contact: ContactInfo) -> int:
        """Create a res.partner record. Returns partner_id."""
        vals = {
            "name": contact.name,
            "phone": contact.phone,
            "email": contact.email,
            "street": contact.address,
            "city": contact.city,
            "zip": contact.zip_code,
            "website": contact.website,
            "is_company": True,
        }
        vals = {k: v for k, v in vals.items() if v}
        partner_id = self._execute("res.partner", "create", [vals])
        logger.info(f"Created res.partner id={partner_id}: {contact.name}")
        return partner_id

    def _create_product(self, item: MenuItem) -> int:
        """Create a product.template available in POS."""
        vals = {
            "name": item.name,
            "description_sale": item.description,
            "list_price": item.price or 0.0,
            "type": "consu",
            "available_in_pos": True,
        }
        if item.category:
            vals["default_code"] = item.category
        vals = {k: v for k, v in vals.items() if v}
        vals["available_in_pos"] = True  # ensure it's always set
        product_id = self._execute("product.template", "create", [vals])
        logger.info(f"Created product.template id={product_id}: {item.name}")
        return product_id

    # Day name → Odoo dayofweek (0=Mon, 1=Tue, ..., 6=Sun)
    _DAY_MAP = {
        "monday": 0, "montag": 0, "lunedì": 0, "lundi": 0,
        "tuesday": 1, "dienstag": 1, "martedì": 1, "mardi": 1,
        "wednesday": 2, "mittwoch": 2, "mercoledì": 2, "mercredi": 2,
        "thursday": 3, "donnerstag": 3, "giovedì": 3, "jeudi": 3,
        "friday": 4, "freitag": 4, "venerdì": 4, "vendredi": 4,
        "saturday": 5, "samstag": 5, "sabato": 5, "samedi": 5,
        "sunday": 6, "sonntag": 6, "domenica": 6, "dimanche": 6,
    }

    def _time_to_float(self, t: str) -> float:
        """Convert 'HH:MM' to float hours (e.g. '14:30' → 14.5)."""
        try:
            h, m = t.split(":")
            return int(h) + int(m) / 60
        except Exception:
            return 0.0

    def _create_business_hours(self, business_name: str, hours: list[BusinessHours]) -> int | None:
        """Create resource.calendar with attendance lines."""
        if not hours:
            return None

        # Filter out closed days and invalid times
        valid = [h for h in hours if not h.closed and h.open_time and h.close_time
                 and h.open_time != "00:00" and h.close_time != "00:00"]
        if not valid:
            return None

        cal_id = self._execute("resource.calendar", "create", [{
            "name": f"Orari {business_name}",
            "tz": "Europe/Zurich",
            "attendance_ids": [],
        }])
        logger.info(f"Created resource.calendar id={cal_id}")

        for h in valid:
            day_num = self._DAY_MAP.get(h.day.lower())
            if day_num is None:
                logger.warning(f"Unknown day '{h.day}', skipping")
                continue

            self._execute("resource.calendar.attendance", "create", [{
                "name": h.day,
                "calendar_id": cal_id,
                "dayofweek": str(day_num),
                "hour_from": self._time_to_float(h.open_time),
                "hour_to": self._time_to_float(h.close_time),
            }])

        logger.info(f"Created {len(valid)} attendance lines for calendar {cal_id}")
        return cal_id

    def _install_modules(self, module_names: list[str]) -> None:
        """Install Odoo modules by technical name."""
        for name in module_names:
            ids = self._execute("ir.module.module", "search", [("name", "=", name)])
            if not ids:
                logger.warning(f"Module '{name}' not found in Odoo, skipping")
                continue

            info = self._execute("ir.module.module", "read", ids, fields=["state"])
            state = info[0]["state"] if info else None

            if state == "installed":
                logger.info(f"Module '{name}' already installed")
                continue

            logger.info(f"Installing module '{name}'...")
            self._execute("ir.module.module", "button_immediate_install", ids)
            logger.info(f"Module '{name}' installed")

    def write_business_data(self, data: BusinessData) -> dict:
        """Write all business data to Odoo. Returns summary of created records."""
        if self.settings.dry_run:
            logger.info("[DRY RUN] Would write to Odoo:")
            logger.info(f"  Contact: {data.contact.name or data.business_name}")
            logger.info(f"  Products: {len(data.menu_items)} items")
            logger.info(f"  Business hours: {len(data.business_hours)} entries")
            logger.info(f"  Modules: {data.modules_suggested}")
            return {
                "dry_run": True,
                "contact_id": None,
                "product_ids": [],
                "calendar_id": None,
                "modules": data.modules_suggested,
            }

        summary = {"dry_run": False, "contact_id": None, "product_ids": [], "modules": [], "calendar_id": None}

        if data.modules_suggested:
            self._install_modules(data.modules_suggested)
            summary["modules"] = data.modules_suggested

        contact = data.contact
        if not contact.name:
            contact.name = data.business_name
        partner_id = self._create_contact(contact)
        summary["contact_id"] = partner_id

        if data.business_hours:
            cal_id = self._create_business_hours(data.business_name, data.business_hours)
            if cal_id:
                summary["calendar_id"] = cal_id

        for item in data.menu_items:
            pid = self._create_product(item)
            summary["product_ids"].append(pid)

        logger.info(f"Write complete: contact={partner_id}, products={len(summary['product_ids'])}, calendar={summary['calendar_id']}")
        return summary
