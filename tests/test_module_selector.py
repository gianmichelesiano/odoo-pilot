# tests/test_module_selector.py
from odoo_pilot.module_selector import select_modules

def test_restaurant_modules():
    modules = select_modules("restaurant")
    assert "base" in modules
    assert "contacts" in modules
    assert "website" in modules
    assert "pos_restaurant" in modules or "lunch" in modules

def test_shop_modules():
    modules = select_modules("shop")
    assert "sale_management" in modules
    assert "stock" in modules

def test_unknown_type_returns_base():
    modules = select_modules("unknown_thing")
    assert "base" in modules
    assert "contacts" in modules
