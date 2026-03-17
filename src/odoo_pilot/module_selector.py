# src/odoo_pilot/module_selector.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MODULE_MAP: dict[str, list[str]] = {
    "restaurant": [
        "base", "contacts", "website", "website_sale",
        "pos_restaurant", "lunch", "calendar", "mail",
    ],
    "cafe": [
        "base", "contacts", "website", "point_of_sale", "calendar", "mail",
    ],
    "bar": [
        "base", "contacts", "website", "point_of_sale", "calendar", "mail",
    ],
    "hotel": [
        "base", "contacts", "website", "website_sale", "calendar", "mail", "sale_management",
    ],
    "shop": [
        "base", "contacts", "website", "website_sale",
        "sale_management", "stock", "purchase", "mail",
    ],
    "service": [
        "base", "contacts", "website", "calendar", "project", "sale_management", "mail",
    ],
}

BASE_MODULES = ["base", "contacts", "website", "mail"]


def select_modules(business_type: str) -> list[str]:
    """Return list of Odoo module names for a given business type."""
    modules = MODULE_MAP.get(business_type.lower(), BASE_MODULES)
    logger.info(f"Selected {len(modules)} modules for business_type={business_type}")
    return modules
