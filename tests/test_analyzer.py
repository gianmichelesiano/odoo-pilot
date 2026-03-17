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


from unittest.mock import patch, MagicMock
from odoo_pilot.analyzer import AIAnalyzer, _build_user_prompt
from odoo_pilot.config import Settings
from odoo_pilot.scraper import PageData


def test_build_user_prompt():
    pages = [
        PageData(url="https://example.com", title="Home", lang="de",
                 text="Welcome to the restaurant", links=[], images=[], scraped_with="playwright"),
        PageData(url="https://example.com/menu", title="Menu", lang="de",
                 text="Pizza Margherita 18.50", links=[], images=[], scraped_with="playwright"),
    ]
    prompt = _build_user_prompt(pages)
    assert "=== PAGE: https://example.com ===" in prompt
    assert "Pizza Margherita" in prompt


def test_analyzer_claude_mock():
    settings = Settings()
    analyzer = AIAnalyzer(settings)

    mock_result = BusinessData(business_name="Test", business_type="restaurant")
    mock_parsed = MagicMock()
    mock_parsed.parsed_output = mock_result

    with patch("odoo_pilot.analyzer.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.parse.return_value = mock_parsed

        pages = [PageData(url="https://x.com", title="T", lang="en",
                          text="A restaurant", links=[], images=[], scraped_with="pw")]
        result = analyzer.analyze(pages)
        assert result.business_name == "Test"
        assert result.business_type == "restaurant"
