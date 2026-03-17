# src/odoo_pilot/pipeline.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from odoo_pilot.analyzer import AIAnalyzer
from odoo_pilot.config import Settings
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
