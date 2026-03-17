import json
from odoo_pilot.scraper import PageData, WebScraper
from odoo_pilot.config import Settings


def test_page_data_to_dict():
    page = PageData(
        url="https://example.com",
        title="Test",
        lang="en",
        text="Hello world",
        links=["https://example.com/about"],
        images=[{"src": "https://example.com/img.jpg", "alt": "test"}],
        scraped_with="playwright",
    )
    d = page.to_dict()
    assert d["url"] == "https://example.com"
    assert d["scraped_with"] == "playwright"
    # Should be JSON-serializable
    json.dumps(d)


def test_normalize_url_basic():
    scraper = WebScraper(Settings())
    base = "https://example.com"
    assert scraper._normalize_url(base, "/about") == "https://example.com/about"
    assert scraper._normalize_url(base, "/about#section") == "https://example.com/about"
    assert scraper._normalize_url(base, "https://other.com/page") is None  # external


def test_normalize_url_www_equiv():
    scraper = WebScraper(Settings())
    base = "https://www.example.com"
    result = scraper._normalize_url(base, "https://example.com/menu")
    assert result == "https://example.com/menu"


def test_normalize_url_trailing_slash():
    scraper = WebScraper(Settings())
    base = "https://example.com"
    url1 = scraper._normalize_url(base, "/menu/")
    url2 = scraper._normalize_url(base, "/menu")
    assert url1 == url2


SAMPLE_HTML = """
<html lang="de">
<head><title>La Qualità</title></head>
<body>
<h1>Willkommen</h1>
<p>Italienisches Restaurant in Zürich</p>
<a href="/menu">Menu</a>
<a href="/kontakt">Kontakt</a>
<a href="https://facebook.com/ext">Facebook</a>
<img src="/img/pasta.jpg" alt="Pasta">
</body>
</html>
"""


def test_parse_html_with_bs4():
    """Test the httpx/BS4 fallback parsing logic."""
    scraper = WebScraper(Settings())
    scraper._base_domain = "https://example.com"
    page = scraper._parse_html("https://example.com", SAMPLE_HTML)
    assert page.title == "La Qualità"
    assert page.lang == "de"
    assert "Willkommen" in page.text
    assert "Italienisches Restaurant" in page.text
    assert page.scraped_with == "httpx"
    assert len(page.images) == 1
    assert page.images[0]["alt"] == "Pasta"
    # External link should be filtered out
    assert all("facebook" not in link for link in page.links)
