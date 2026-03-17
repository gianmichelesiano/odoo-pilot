# OdooPilot Phases 1-3 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that scrapes a business website, analyzes it with AI, and populates an Odoo 19 instance via XML-RPC.

**Architecture:** Monolithic Python package with 4 modules: scraper (Playwright + httpx fallback), analyzer (Claude API + Ollama fallback using Pydantic structured output), module_selector (business_type → Odoo modules mapping), and odoo_writer (XML-RPC client). A pipeline orchestrator ties them together with dry_run=True default.

**Tech Stack:** Python 3.12+, Playwright, httpx, BeautifulSoup4, anthropic SDK (messages.parse + Pydantic), ollama, xmlrpc.client (stdlib), rich, argparse

---

## File Structure

```
~/Development/odoo-pilot/
├── pyproject.toml
├── .gitignore
├── src/
│   └── odoo_pilot/
│       ├── __init__.py          # version
│       ├── __main__.py          # CLI entry point
│       ├── config.py            # Settings dataclass
│       ├── scraper.py           # WebScraper + PageData (Phase 1)
│       ├── analyzer.py          # AIAnalyzer + BusinessData (Phase 2)
│       ├── models.py            # Shared Pydantic models for AI output (Phase 2)
│       ├── module_selector.py   # business_type → Odoo modules (Phase 3)
│       ├── odoo_writer.py       # OdooWriter XML-RPC client (Phase 3)
│       └── pipeline.py          # Orchestrator: scrape → analyze → write (Phase 3)
├── tests/
│   ├── test_scraper.py
│   ├── test_analyzer.py
│   ├── test_module_selector.py
│   ├── test_odoo_writer.py
│   └── test_pipeline.py
└── output/                      # JSON output (gitignored)
```

---

## PHASE 1: Setup & Scraper

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/odoo_pilot/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p ~/Development/odoo-pilot/src/odoo_pilot ~/Development/odoo-pilot/tests ~/Development/odoo-pilot/output
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "odoo-pilot"
version = "0.1.0"
description = "CLI tool to scrape websites and populate Odoo 19"
requires-python = ">=3.12"
dependencies = [
    "playwright>=1.40",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "rich>=13.0",
]

[project.optional-dependencies]
ai = ["anthropic>=0.40", "ollama>=0.4", "pydantic>=2.0"]
odoo = []  # no extra deps, uses stdlib xmlrpc.client
all = ["odoo-pilot[ai]"]

[project.scripts]
odoo-pilot = "odoo_pilot.__main__:main"
```

- [ ] **Step 3: Write .gitignore**

```
output/
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.eggs/
```

- [ ] **Step 4: Write __init__.py**

```python
"""OdooPilot — scrape websites, analyze with AI, populate Odoo 19."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Init git repo and commit**

```bash
cd ~/Development/odoo-pilot
git init
git add pyproject.toml .gitignore src/odoo_pilot/__init__.py
git commit -m "chore: initial project scaffolding"
```

---

### Task 2: config.py

**Files:**
- Create: `src/odoo_pilot/config.py`
- Create: `tests/test_config.py` (minimal)

- [ ] **Step 1: Write test for Settings defaults**

```python
# tests/test_config.py
from pathlib import Path
from odoo_pilot.config import Settings

def test_settings_defaults():
    s = Settings()
    assert s.dry_run is True
    assert s.playwright_timeout == 30000
    assert s.max_pages == 50
    assert s.request_delay == 1.0
    assert s.output_dir == Path("output")

def test_settings_override():
    s = Settings(max_pages=10, dry_run=False)
    assert s.max_pages == 10
    assert s.dry_run is False
```

- [ ] **Step 2: Run test — should fail (module doesn't exist)**

```bash
cd ~/Development/odoo-pilot && python -m pytest tests/test_config.py -v
```

- [ ] **Step 3: Write config.py**

```python
# src/odoo_pilot/config.py
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    dry_run: bool = True
    playwright_timeout: int = 30000  # ms
    max_pages: int = 50
    request_delay: float = 1.0  # seconds between page requests
    output_dir: Path = field(default_factory=lambda: Path("output"))

    # Odoo connection (Phase 3)
    odoo_url: str = ""
    odoo_db: str = ""
    odoo_user: str = ""
    odoo_password: str = ""

    # AI config (Phase 2)
    anthropic_model: str = "claude-sonnet-4-5"
    ollama_model: str = "llama3.1"
    use_ollama: bool = False  # fallback flag
```

- [ ] **Step 4: Run test — should pass**

```bash
python -m pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/odoo_pilot/config.py tests/test_config.py
git commit -m "feat: add Settings dataclass with defaults"
```

---

### Task 3: scraper.py — PageData + URL Normalization

**Files:**
- Create: `src/odoo_pilot/scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write tests for PageData and URL normalization**

```python
# tests/test_scraper.py
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
```

- [ ] **Step 2: Run tests — should fail**

```bash
python -m pytest tests/test_scraper.py -v
```

- [ ] **Step 3: Write PageData dataclass and URL normalization**

```python
# src/odoo_pilot/scraper.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from odoo_pilot.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class PageData:
    url: str
    title: str
    lang: str
    text: str
    links: list[str]
    images: list[dict[str, str]]
    scraped_with: str

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "lang": self.lang,
            "text": self.text,
            "links": self.links,
            "images": self.images,
            "scraped_with": self.scraped_with,
        }


class WebScraper:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._base_domain: str = ""

    def _normalize_url(self, base: str, href: str) -> str | None:
        """Resolve, normalize, and filter URL. Returns None if external."""
        resolved = urljoin(base, href)
        parsed = urlparse(resolved)

        # Strip fragments
        cleaned = parsed._replace(fragment="")

        # Strip trailing slash from path
        path = cleaned.path.rstrip("/") or "/"
        cleaned = cleaned._replace(path=path)

        # Normalize www
        host = cleaned.hostname or ""
        base_host = urlparse(base).hostname or ""
        host_bare = host.removeprefix("www.")
        base_bare = base_host.removeprefix("www.")

        if host_bare != base_bare:
            return None  # external link

        # Reconstruct with bare domain (no www)
        cleaned = cleaned._replace(netloc=host_bare)
        return urlunparse(cleaned)
```

- [ ] **Step 4: Run tests — should pass**

```bash
python -m pytest tests/test_scraper.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/odoo_pilot/scraper.py tests/test_scraper.py
git commit -m "feat: add PageData and URL normalization"
```

---

### Task 4: scraper.py — Playwright + httpx Crawl

**Files:**
- Modify: `src/odoo_pilot/scraper.py`
- Modify: `tests/test_scraper.py`

- [ ] **Step 1: Write unit test for httpx fallback (mocked HTML)**

```python
# append to tests/test_scraper.py
import pytest

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
```

- [ ] **Step 2: Run test — should fail (method doesn't exist)**

```bash
python -m pytest tests/test_scraper.py::test_parse_html_with_bs4 -v
```

- [ ] **Step 3: Implement full scraper methods**

Add to `scraper.py`:

```python
    def _parse_html(self, url: str, html: str) -> PageData:
        """Parse raw HTML with BeautifulSoup (used by httpx fallback)."""
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        lang = soup.find("html").get("lang", "") if soup.find("html") else ""
        text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""

        links = []
        for a in soup.find_all("a", href=True):
            normalized = self._normalize_url(url, a["href"])
            if normalized and normalized not in links:
                links.append(normalized)

        images = []
        for img in soup.find_all("img", src=True):
            images.append({
                "src": urljoin(url, img["src"]),
                "alt": img.get("alt", ""),
            })

        return PageData(
            url=url, title=title, lang=lang, text=text,
            links=links, images=images, scraped_with="httpx",
        )

    async def _scrape_page_httpx(self, url: str) -> PageData | None:
        """Fallback scraper using httpx + BeautifulSoup."""
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, timeout=self.settings.playwright_timeout / 1000)
                resp.raise_for_status()
                return self._parse_html(url, resp.text)
        except Exception as e:
            logger.error(f"httpx fallback failed for {url}: {e}")
            return None

    async def _scrape_page_playwright(self, page, url: str) -> PageData | None:
        """Scrape a single page with Playwright."""
        try:
            await page.goto(url, wait_until="networkidle",
                            timeout=self.settings.playwright_timeout)
            title = await page.title()
            lang = await page.get_attribute("html", "lang") or ""
            text = await page.inner_text("body")

            # Extract links
            hrefs = await page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.getAttribute('href'))"
            )
            links = []
            for href in hrefs:
                normalized = self._normalize_url(url, href)
                if normalized and normalized not in links:
                    links.append(normalized)

            # Extract images
            imgs = await page.eval_on_selector_all(
                "img[src]",
                "els => els.map(e => ({src: e.src, alt: e.alt || ''}))"
            )

            return PageData(
                url=url, title=title, lang=lang, text=text,
                links=links, images=imgs, scraped_with="playwright",
            )
        except Exception as e:
            logger.warning(f"Playwright failed for {url}: {e}")
            return None

    async def scrape(self, url: str) -> list[PageData]:
        """Scrape a website starting from url. Returns list of PageData."""
        self._base_domain = url.rstrip("/")
        pages: list[PageData] = []
        visited: set[str] = set()
        to_visit: list[str] = [self._normalize_url(url, url) or url]

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed, using httpx only")
            async_playwright = None

        pw = None
        browser = None
        pw_page = None

        try:
            if async_playwright:
                pw = await async_playwright().__aenter__()
                browser = await pw.chromium.launch(headless=True)
                pw_page = await browser.new_page()

            while to_visit and len(pages) < self.settings.max_pages:
                current_url = to_visit.pop(0)
                if current_url in visited:
                    continue
                visited.add(current_url)

                page_data = None

                # Try Playwright first
                if pw_page:
                    page_data = await self._scrape_page_playwright(pw_page, current_url)

                # Fallback to httpx
                if page_data is None:
                    page_data = await self._scrape_page_httpx(current_url)

                if page_data is None:
                    logger.error(f"Skipping {current_url}: both engines failed")
                    continue

                pages.append(page_data)
                logger.info(f"[{page_data.scraped_with}] {current_url} — {len(page_data.text)} chars")

                # Add new links to queue
                for link in page_data.links:
                    if link not in visited and link not in to_visit:
                        to_visit.append(link)

                # Politeness delay
                if to_visit:
                    await asyncio.sleep(self.settings.request_delay)

        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.__aexit__(None, None, None)

        if not pages:
            raise RuntimeError(f"No pages scraped from {url}")

        return pages
```

- [ ] **Step 4: Run all scraper tests — should pass**

```bash
python -m pytest tests/test_scraper.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/odoo_pilot/scraper.py tests/test_scraper.py
git commit -m "feat: implement WebScraper with Playwright + httpx fallback"
```

---

### Task 5: __main__.py — CLI

**Files:**
- Create: `src/odoo_pilot/__main__.py`

- [ ] **Step 1: Write __main__.py**

```python
# src/odoo_pilot/__main__.py
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console
from rich.logging import RichHandler

from odoo_pilot.config import Settings
from odoo_pilot.scraper import WebScraper


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


def parse_args(argv: list[str] | None = None):
    import argparse

    parser = argparse.ArgumentParser(prog="odoo-pilot", description="Scrape websites and populate Odoo 19")
    sub = parser.add_subparsers(dest="command")

    scrape = sub.add_parser("scrape", help="Scrape a website")
    scrape.add_argument("url", help="Base URL to scrape")
    scrape.add_argument("--max-pages", type=int, default=50)
    scrape.add_argument("--output-dir", type=Path, default=Path("output"))
    scrape.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")

    return parser.parse_args(argv)


async def cmd_scrape(args) -> None:
    console = Console()
    settings = Settings(
        max_pages=args.max_pages,
        output_dir=args.output_dir,
        request_delay=args.delay,
    )

    scraper = WebScraper(settings)
    console.print(f"[bold]Scraping[/bold] {args.url} (max {settings.max_pages} pages)...")

    pages = await scraper.scrape(args.url)

    # Save output
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    domain = urlparse(args.url).hostname or "unknown"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = settings.output_dir / f"{domain}_{timestamp}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in pages], f, ensure_ascii=False, indent=2)

    console.print(f"\n[bold green]Done![/bold green] {len(pages)} pages scraped → {out_path}")


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = parse_args(argv)

    if args.command == "scrape":
        asyncio.run(cmd_scrape(args))
    else:
        parse_args(["--help"])
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add src/odoo_pilot/__main__.py
git commit -m "feat: add CLI entry point with scrape command"
```

---

### Task 6: Install & Live Test

- [ ] **Step 1: Create venv and install**

```bash
cd ~/Development/odoo-pilot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[ai]"
playwright install chromium
```

- [ ] **Step 2: Run unit tests**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 3: Run live scrape on laqualita.ch**

```bash
python -m odoo_pilot scrape https://laqualita.ch --max-pages 15
```

Expected: JSON file in `output/laqualita.ch_*.json` with multiple pages, each with non-empty text.

- [ ] **Step 4: Inspect output and commit**

```bash
cat output/laqualita.ch_*.json | python -m json.tool | head -50
git add -A && git commit -m "feat: Phase 1 complete — scraper working on laqualita.ch"
```

---

## PHASE 2: AI Analyzer

### Task 7: models.py — Pydantic Models for AI Output

**Files:**
- Create: `src/odoo_pilot/models.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write Pydantic models**

```python
# src/odoo_pilot/models.py
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
```

- [ ] **Step 2: Write test for model serialization**

```python
# tests/test_analyzer.py
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
```

- [ ] **Step 3: Run tests — should pass**

```bash
python -m pytest tests/test_analyzer.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/odoo_pilot/models.py tests/test_analyzer.py
git commit -m "feat: add Pydantic models for AI-structured business data"
```

---

### Task 8: analyzer.py — Claude API + Ollama Fallback

**Files:**
- Create: `src/odoo_pilot/analyzer.py`
- Modify: `tests/test_analyzer.py`

- [ ] **Step 1: Write analyzer.py**

```python
# src/odoo_pilot/analyzer.py
from __future__ import annotations

import json
import logging

from odoo_pilot.config import Settings
from odoo_pilot.models import BusinessData
from odoo_pilot.scraper import PageData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a business data extraction expert. Analyze the raw text from a scraped website and extract structured business information.

Focus on:
- Business name and type (restaurant, hotel, shop, etc.)
- Contact info (phone, email, address, city, zip, country)
- Menu items with prices and categories (if applicable)
- Business/opening hours
- Social media links
- Key tags/keywords describing the business
- Suggested Odoo 19 modules based on business type

Rules:
- Extract ONLY information that is explicitly present in the text
- Prices should be numeric (no currency symbols)
- Hours should be in HH:MM format
- If information is missing, leave the field empty/default
- For business_type, use one of: restaurant, hotel, shop, service, cafe, bar, other
"""


def _build_user_prompt(pages: list[PageData]) -> str:
    """Combine all page texts into a single prompt."""
    parts = []
    for page in pages:
        parts.append(f"=== PAGE: {page.url} ===\nTitle: {page.title}\n\n{page.text}\n")
    return "\n".join(parts)


class AIAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze(self, pages: list[PageData]) -> BusinessData:
        """Analyze scraped pages and return structured BusinessData."""
        user_prompt = _build_user_prompt(pages)

        if not self.settings.use_ollama:
            try:
                return self._analyze_claude(user_prompt)
            except Exception as e:
                logger.warning(f"Claude API failed: {e}, falling back to Ollama")

        return self._analyze_ollama(user_prompt)

    def _analyze_claude(self, user_prompt: str) -> BusinessData:
        """Use Anthropic SDK with structured output (messages.parse)."""
        import anthropic

        client = anthropic.Anthropic()
        logger.info(f"Calling Claude ({self.settings.anthropic_model})...")

        parsed = client.messages.parse(
            model=self.settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            output_format=BusinessData,
            messages=[{"role": "user", "content": user_prompt}],
        )

        result = parsed.parsed_output
        logger.info(f"Claude extracted: {result.business_name} ({result.business_type})")
        return result

    def _analyze_ollama(self, user_prompt: str) -> BusinessData:
        """Fallback: use Ollama with JSON mode."""
        import ollama

        logger.info(f"Calling Ollama ({self.settings.ollama_model})...")

        response = ollama.chat(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n\nRespond with valid JSON matching the BusinessData schema."},
                {"role": "user", "content": user_prompt},
            ],
            format="json",
        )

        raw = json.loads(response["message"]["content"])
        result = BusinessData.model_validate(raw)
        logger.info(f"Ollama extracted: {result.business_name} ({result.business_type})")
        return result
```

- [ ] **Step 2: Write unit test with mocked Claude response**

```python
# append to tests/test_analyzer.py
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
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_analyzer.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/odoo_pilot/analyzer.py tests/test_analyzer.py
git commit -m "feat: add AIAnalyzer with Claude + Ollama fallback"
```

---

### Task 9: Add `analyze` CLI Command + Live Test

**Files:**
- Modify: `src/odoo_pilot/__main__.py`

- [ ] **Step 1: Add analyze subcommand to CLI**

Add to `__main__.py` after the scrape subparser:

```python
    analyze = sub.add_parser("analyze", help="Analyze scraped JSON with AI")
    analyze.add_argument("input_file", type=Path, help="Path to scraper output JSON")
    analyze.add_argument("--output-dir", type=Path, default=Path("output"))
    analyze.add_argument("--ollama", action="store_true", help="Use Ollama instead of Claude")
    analyze.add_argument("--model", type=str, default=None, help="Override AI model name")
```

Add `cmd_analyze` function:

```python
async def cmd_analyze(args) -> None:
    from odoo_pilot.analyzer import AIAnalyzer
    from odoo_pilot.models import BusinessData
    from odoo_pilot.scraper import PageData

    console = Console()

    # Load scraper output
    with open(args.input_file, encoding="utf-8") as f:
        raw_pages = json.load(f)
    pages = [PageData(**p) for p in raw_pages]
    console.print(f"[bold]Analyzing[/bold] {len(pages)} pages from {args.input_file}...")

    settings = Settings(use_ollama=args.ollama)
    if args.model:
        if args.ollama:
            settings.ollama_model = args.model
        else:
            settings.anthropic_model = args.model

    analyzer = AIAnalyzer(settings)
    result = analyzer.analyze(pages)

    # Save output
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / args.input_file.stem.replace("_scraped", "") + "_analyzed.json"
    # Simpler: derive from input filename
    stem = args.input_file.stem
    out_path = args.output_dir / f"{stem}_analyzed.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

    console.print(f"\n[bold green]Done![/bold green] {result.business_name} ({result.business_type}) → {out_path}")
    if result.menu_items:
        console.print(f"  Menu items: {len(result.menu_items)}")
    if result.business_hours:
        console.print(f"  Business hours: {len(result.business_hours)} entries")
```

Add to `main()`:

```python
    elif args.command == "analyze":
        asyncio.run(cmd_analyze(args))
```

- [ ] **Step 2: Live test — analyze the scraper output with Claude**

```bash
# Use the JSON from Phase 1 live test
python -m odoo_pilot analyze output/laqualita.ch_*.json
```

Expected: `output/*_analyzed.json` with structured BusinessData (business_name, menu_items, hours, contact).

- [ ] **Step 3: Inspect output and commit**

```bash
cat output/*_analyzed.json | python -m json.tool | head -80
git add -A && git commit -m "feat: Phase 2 complete — AI analyzer with Claude + Ollama"
```

---

## PHASE 3: Module Selector + Odoo Writer

### Task 10: module_selector.py

**Files:**
- Create: `src/odoo_pilot/module_selector.py`
- Create: `tests/test_module_selector.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_module_selector.py
from odoo_pilot.module_selector import select_modules

def test_restaurant_modules():
    modules = select_modules("restaurant")
    assert "base" in modules
    assert "contacts" in modules
    assert "website" in modules
    assert "lunch" in modules or "pos_restaurant" in modules

def test_shop_modules():
    modules = select_modules("shop")
    assert "sale_management" in modules
    assert "stock" in modules

def test_unknown_type_returns_base():
    modules = select_modules("unknown_thing")
    assert "base" in modules
    assert "contacts" in modules
```

- [ ] **Step 2: Run tests — should fail**

```bash
python -m pytest tests/test_module_selector.py -v
```

- [ ] **Step 3: Write module_selector.py**

```python
# src/odoo_pilot/module_selector.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Mapping: business_type → list of Odoo 19 module technical names
MODULE_MAP: dict[str, list[str]] = {
    "restaurant": [
        "base",
        "contacts",
        "website",
        "website_sale",
        "pos_restaurant",
        "lunch",
        "calendar",
        "mail",
    ],
    "cafe": [
        "base",
        "contacts",
        "website",
        "point_of_sale",
        "calendar",
        "mail",
    ],
    "bar": [
        "base",
        "contacts",
        "website",
        "point_of_sale",
        "calendar",
        "mail",
    ],
    "hotel": [
        "base",
        "contacts",
        "website",
        "website_sale",
        "calendar",
        "mail",
        "sale_management",
    ],
    "shop": [
        "base",
        "contacts",
        "website",
        "website_sale",
        "sale_management",
        "stock",
        "purchase",
        "mail",
    ],
    "service": [
        "base",
        "contacts",
        "website",
        "calendar",
        "project",
        "sale_management",
        "mail",
    ],
}

BASE_MODULES = ["base", "contacts", "website", "mail"]


def select_modules(business_type: str) -> list[str]:
    """Return list of Odoo module names for a given business type."""
    modules = MODULE_MAP.get(business_type.lower(), BASE_MODULES)
    logger.info(f"Selected {len(modules)} modules for business_type={business_type}")
    return modules
```

- [ ] **Step 4: Run tests — should pass**

```bash
python -m pytest tests/test_module_selector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/odoo_pilot/module_selector.py tests/test_module_selector.py
git commit -m "feat: add module_selector with business_type → Odoo modules mapping"
```

---

### Task 11: odoo_writer.py — XML-RPC Client

**Files:**
- Create: `src/odoo_pilot/odoo_writer.py`
- Create: `tests/test_odoo_writer.py`

- [ ] **Step 1: Write tests (mocked XML-RPC)**

```python
# tests/test_odoo_writer.py
from unittest.mock import patch, MagicMock
from odoo_pilot.odoo_writer import OdooWriter
from odoo_pilot.config import Settings
from odoo_pilot.models import BusinessData, ContactInfo, MenuItem, BusinessHours


def _test_settings():
    return Settings(
        odoo_url="http://localhost:8069",
        odoo_db="test",
        odoo_user="admin",
        odoo_password="admin",
        dry_run=False,
    )


def test_authenticate_success():
    settings = _test_settings()
    with patch("xmlrpc.client.ServerProxy") as mock_proxy:
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 2  # uid
        mock_proxy.return_value = mock_common

        writer = OdooWriter(settings)
        writer.authenticate()
        assert writer.uid == 2


def test_dry_run_skips_write():
    settings = _test_settings()
    settings.dry_run = True
    writer = OdooWriter(settings)
    writer.uid = 2

    data = BusinessData(business_name="Test", business_type="restaurant")
    # Should not raise, should log and skip
    writer.write_business_data(data)


def test_create_contact():
    settings = _test_settings()
    writer = OdooWriter(settings)
    writer.uid = 2
    writer._models = MagicMock()
    writer._models.execute_kw.return_value = 42

    contact = ContactInfo(
        name="La Qualità",
        phone="+41 44 123 45 67",
        email="info@laqualita.ch",
        address="Hauptstrasse 1",
        city="Zürich",
        zip_code="8001",
        country="Switzerland",
        website="https://laqualita.ch",
    )

    partner_id = writer._create_contact(contact)
    assert partner_id == 42
    writer._models.execute_kw.assert_called_once()
```

- [ ] **Step 2: Run tests — should fail**

```bash
python -m pytest tests/test_odoo_writer.py -v
```

- [ ] **Step 3: Write odoo_writer.py**

```python
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
        # Remove empty values
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
            "type": "consu",  # consumable
        }
        if item.category:
            vals["default_code"] = item.category  # use as internal ref

        vals = {k: v for k, v in vals.items() if v}
        product_id = self._execute("product.template", "create", [vals])
        logger.info(f"Created product.template id={product_id}: {item.name}")
        return product_id

    def _install_modules(self, module_names: list[str]) -> None:
        """Install Odoo modules by technical name."""
        for name in module_names:
            # Find module
            ids = self._execute(
                "ir.module.module", "search",
                [("name", "=", name)],
            )
            if not ids:
                logger.warning(f"Module '{name}' not found in Odoo, skipping")
                continue

            # Check state
            info = self._execute(
                "ir.module.module", "read",
                ids, {"fields": ["state"]},
            )
            state = info[0]["state"] if info else None

            if state == "installed":
                logger.info(f"Module '{name}' already installed")
                continue

            # Install
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
            return {"dry_run": True, "contact_id": None, "product_ids": [], "modules": data.modules_suggested}

        summary = {"dry_run": False, "contact_id": None, "product_ids": [], "modules": []}

        # 1. Install modules
        if data.modules_suggested:
            self._install_modules(data.modules_suggested)
            summary["modules"] = data.modules_suggested

        # 2. Create contact
        contact = data.contact
        if not contact.name:
            contact.name = data.business_name
        partner_id = self._create_contact(contact)
        summary["contact_id"] = partner_id

        # 3. Create products (menu items)
        for item in data.menu_items:
            pid = self._create_product(item)
            summary["product_ids"].append(pid)

        logger.info(f"Write complete: contact={partner_id}, products={len(summary['product_ids'])}")
        return summary
```

- [ ] **Step 4: Run tests — should pass**

```bash
python -m pytest tests/test_odoo_writer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/odoo_pilot/odoo_writer.py tests/test_odoo_writer.py
git commit -m "feat: add OdooWriter XML-RPC client with dry_run support"
```

---

### Task 12: pipeline.py — Orchestrator

**Files:**
- Create: `src/odoo_pilot/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write pipeline.py**

```python
# src/odoo_pilot/pipeline.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from odoo_pilot.analyzer import AIAnalyzer
from odoo_pilot.config import Settings
from odoo_pilot.models import BusinessData
from odoo_pilot.module_selector import select_modules
from odoo_pilot.odoo_writer import OdooWriter
from odoo_pilot.scraper import WebScraper

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def run(self, url: str) -> dict:
        """Run the full pipeline: scrape → analyze → select modules → write to Odoo."""
        domain = urlparse(url).hostname or "unknown"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Scrape
        logger.info("=== STEP 1: Scraping ===")
        scraper = WebScraper(self.settings)
        pages = await scraper.scrape(url)

        scrape_path = self.settings.output_dir / f"{domain}_{timestamp}_scraped.json"
        with open(scrape_path, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in pages], f, ensure_ascii=False, indent=2)
        logger.info(f"Scraped {len(pages)} pages → {scrape_path}")

        # Step 2: Analyze
        logger.info("=== STEP 2: AI Analysis ===")
        analyzer = AIAnalyzer(self.settings)
        business_data = analyzer.analyze(pages)

        # Step 3: Select modules
        logger.info("=== STEP 3: Module Selection ===")
        modules = select_modules(business_data.business_type)
        business_data.modules_suggested = modules

        analysis_path = self.settings.output_dir / f"{domain}_{timestamp}_analyzed.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(business_data.model_dump(), f, ensure_ascii=False, indent=2)
        logger.info(f"Analysis → {analysis_path}")

        # Step 4: Write to Odoo
        logger.info("=== STEP 4: Odoo Write ===")
        writer = OdooWriter(self.settings)
        if not self.settings.dry_run:
            writer.authenticate()
        summary = writer.write_business_data(business_data)

        summary_path = self.settings.output_dir / f"{domain}_{timestamp}_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary
```

- [ ] **Step 2: Write test (mocked pipeline)**

```python
# tests/test_pipeline.py
from odoo_pilot.pipeline import Pipeline
from odoo_pilot.config import Settings

def test_pipeline_import():
    """Verify pipeline can be instantiated."""
    settings = Settings(dry_run=True)
    p = Pipeline(settings)
    assert p.settings.dry_run is True
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_pipeline.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/odoo_pilot/pipeline.py tests/test_pipeline.py
git commit -m "feat: add Pipeline orchestrator (scrape → analyze → write)"
```

---

### Task 13: Add `run` CLI Command + Full Pipeline Test

**Files:**
- Modify: `src/odoo_pilot/__main__.py`

- [ ] **Step 1: Add `run` subcommand**

Add to CLI parser:

```python
    run_cmd = sub.add_parser("run", help="Full pipeline: scrape → analyze → write to Odoo")
    run_cmd.add_argument("url", help="Base URL to scrape")
    run_cmd.add_argument("--max-pages", type=int, default=50)
    run_cmd.add_argument("--output-dir", type=Path, default=Path("output"))
    run_cmd.add_argument("--delay", type=float, default=1.0)
    run_cmd.add_argument("--ollama", action="store_true", help="Use Ollama instead of Claude")
    run_cmd.add_argument("--odoo-url", type=str, default="")
    run_cmd.add_argument("--odoo-db", type=str, default="")
    run_cmd.add_argument("--odoo-user", type=str, default="")
    run_cmd.add_argument("--odoo-password", type=str, default="")
    run_cmd.add_argument("--no-dry-run", action="store_true", help="Actually write to Odoo (default: dry run)")
```

Add `cmd_run` function:

```python
async def cmd_run(args) -> None:
    from odoo_pilot.pipeline import Pipeline

    console = Console()
    settings = Settings(
        max_pages=args.max_pages,
        output_dir=args.output_dir,
        request_delay=args.delay,
        use_ollama=args.ollama,
        dry_run=not args.no_dry_run,
        odoo_url=args.odoo_url,
        odoo_db=args.odoo_db,
        odoo_user=args.odoo_user,
        odoo_password=args.odoo_password,
    )

    console.print(f"[bold]Running full pipeline[/bold] on {args.url}")
    console.print(f"  dry_run={settings.dry_run}, ollama={settings.use_ollama}")

    pipeline = Pipeline(settings)
    summary = await pipeline.run(args.url)

    console.print(f"\n[bold green]Pipeline complete![/bold green]")
    console.print(f"  dry_run: {summary.get('dry_run')}")
    console.print(f"  contact_id: {summary.get('contact_id')}")
    console.print(f"  products: {len(summary.get('product_ids', []))}")
    console.print(f"  modules: {summary.get('modules', [])}")
```

- [ ] **Step 2: Test dry run on laqualita.ch**

```bash
python -m odoo_pilot run https://laqualita.ch --max-pages 10
```

Expected: Full pipeline runs, dry_run=True, JSON files saved in output/, no Odoo writes.

- [ ] **Step 3: Test live Odoo write (with real credentials)**

```bash
python -m odoo_pilot run https://laqualita.ch --max-pages 10 \
  --odoo-url http://100.90.71.20:8069 \
  --odoo-db laqualita \
  --odoo-user bandigare@gmail.com \
  --odoo-password Wolfgang-75 \
  --no-dry-run
```

Expected: Modules installed, contact created, products created in Odoo.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: Phase 3 complete — full pipeline with Odoo write"
```

---

## Verification Checklist

1. `python -m pytest tests/ -v` — all tests pass
2. `python -m odoo_pilot scrape https://laqualita.ch` — produces JSON with pages
3. `python -m odoo_pilot analyze output/*.json` — produces structured BusinessData
4. `python -m odoo_pilot run https://laqualita.ch` — full dry-run pipeline works
5. `python -m odoo_pilot run https://laqualita.ch --no-dry-run --odoo-url ...` — writes to Odoo
6. Odoo instance at http://100.90.71.20:8069 has new contacts and products
