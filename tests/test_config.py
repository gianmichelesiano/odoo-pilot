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
