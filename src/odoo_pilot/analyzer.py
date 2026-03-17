from __future__ import annotations

import json
import logging

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

try:
    import ollama
except ImportError:
    ollama = None  # type: ignore[assignment]

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

        if ollama is None:
            raise RuntimeError("Ollama not installed. Run: pip install ollama")
        return self._analyze_ollama(user_prompt)

    def _analyze_claude(self, user_prompt: str) -> BusinessData:
        """Use Anthropic SDK — prompt Claude to return JSON, validate with Pydantic."""
        import httpx
        client = anthropic.Anthropic(timeout=httpx.Timeout(60.0, connect=10.0))
        logger.info(f"Calling Claude ({self.settings.anthropic_model})... (attendere ~10-20s)")

        schema = BusinessData.model_json_schema()
        json_instruction = (
            f"\n\nRespond with ONLY valid JSON matching this schema (no markdown, no explanation):\n{json.dumps(schema, indent=2)}"
        )

        response = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt + json_instruction}],
        )

        raw = json.loads(response.content[0].text)
        result = BusinessData.model_validate(raw)
        logger.info(f"Claude extracted: {result.business_name} ({result.business_type})")
        return result

    def _analyze_ollama(self, user_prompt: str) -> BusinessData:
        """Fallback: use Ollama with JSON mode."""
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
