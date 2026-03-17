from odoo_pilot.models import BusinessData, ContactInfo, MenuItem

def test_business_data_minimal():
    bd = BusinessData(business_name="La Qualità", business_type="restaurant")
    d = bd.model_dump()
    assert d["business_name"] == "La Qualità"
    assert d["business_type"] == "restaurant"
    assert d["menu_items"] == []

def test_business_data_full():
    bd = BusinessData(
        business_name="La Qualità",
        business_type="restaurant",
        contact=ContactInfo(phone="+41 44 123 45 67", city="Zürich"),
        menu_items=[MenuItem(name="Margherita", price=18.50, category="Pizza")],
    )
    assert bd.contact.city == "Zürich"
    assert bd.menu_items[0].price == 18.50
