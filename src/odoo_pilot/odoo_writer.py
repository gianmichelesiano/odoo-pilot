# src/odoo_pilot/odoo_writer.py
from __future__ import annotations

import logging
import xmlrpc.client

from odoo_pilot.config import Settings
from odoo_pilot.models import BusinessData, ContactInfo, MenuItem

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
        """Create a product.template record for a menu item."""
        vals = {
            "name": item.name,
            "description_sale": item.description,
            "list_price": item.price or 0.0,
            "type": "consu",
        }
        if item.category:
            vals["default_code"] = item.category
        vals = {k: v for k, v in vals.items() if v}
        product_id = self._execute("product.template", "create", [vals])
        logger.info(f"Created product.template id={product_id}: {item.name}")
        return product_id

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
            logger.info(f"  Modules: {data.modules_suggested}")
            return {
                "dry_run": True,
                "contact_id": None,
                "product_ids": [],
                "modules": data.modules_suggested,
            }

        summary = {"dry_run": False, "contact_id": None, "product_ids": [], "modules": []}

        if data.modules_suggested:
            self._install_modules(data.modules_suggested)
            summary["modules"] = data.modules_suggested

        contact = data.contact
        if not contact.name:
            contact.name = data.business_name
        partner_id = self._create_contact(contact)
        summary["contact_id"] = partner_id

        for item in data.menu_items:
            pid = self._create_product(item)
            summary["product_ids"].append(pid)

        logger.info(f"Write complete: contact={partner_id}, products={len(summary['product_ids'])}")
        return summary
