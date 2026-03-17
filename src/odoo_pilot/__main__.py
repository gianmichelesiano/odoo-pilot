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

    analyze = sub.add_parser("analyze", help="Analyze scraped JSON with AI")
    analyze.add_argument("input_file", type=Path, help="Path to scraper output JSON")
    analyze.add_argument("--output-dir", type=Path, default=Path("output"))
    analyze.add_argument("--ollama", action="store_true", help="Use Ollama instead of Claude")
    analyze.add_argument("--model", type=str, default=None, help="Override AI model name")

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


def cmd_analyze(args) -> None:
    from odoo_pilot.analyzer import AIAnalyzer
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
    stem = args.input_file.stem
    out_path = args.output_dir / f"{stem}_analyzed.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

    console.print(f"\n[bold green]Done![/bold green] {result.business_name} ({result.business_type}) → {out_path}")
    if result.menu_items:
        console.print(f"  Menu items: {len(result.menu_items)}")
    if result.business_hours:
        console.print(f"  Business hours: {len(result.business_hours)} entries")


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = parse_args(argv)

    if args.command == "scrape":
        asyncio.run(cmd_scrape(args))
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parse_args(["--help"])
        sys.exit(1)


if __name__ == "__main__":
    main()
