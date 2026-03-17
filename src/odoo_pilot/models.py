from __future__ import annotations
from pydantic import BaseModel


class ContactInfo(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    zip_code: str = ""
    country: str = ""
    website: str = ""


class MenuItem(BaseModel):
    name: str
    description: str = ""
    price: float | None = None
    category: str = ""  # e.g. "Antipasti", "Pasta", "Dessert"


class BusinessHours(BaseModel):
    day: str          # e.g. "Monday", "Montag"
    open_time: str    # e.g. "11:30"
    close_time: str   # e.g. "22:00"
    closed: bool = False


class BusinessData(BaseModel):
    """Structured output from AI analysis of scraped website."""
    business_name: str
    business_type: str              # e.g. "restaurant", "hotel", "shop"
    description: str = ""
    languages: list[str] = []       # detected languages on the site
    contact: ContactInfo = ContactInfo()
    menu_items: list[MenuItem] = []
    business_hours: list[BusinessHours] = []
    social_media: dict[str, str] = {}  # {"instagram": "url", "facebook": "url"}
    tags: list[str] = []            # e.g. ["italian", "pizza", "zurich"]
    modules_suggested: list[str] = []  # AI suggestion for Odoo modules
