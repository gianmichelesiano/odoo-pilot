from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
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

        pw_ctx = None
        pw = None
        browser = None
        pw_page = None

        try:
            if async_playwright:
                pw_ctx = async_playwright()
                pw = await pw_ctx.__aenter__()
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
            if pw_ctx:
                await pw_ctx.__aexit__(None, None, None)

        if not pages:
            raise RuntimeError(f"No pages scraped from {url}")

        return pages
