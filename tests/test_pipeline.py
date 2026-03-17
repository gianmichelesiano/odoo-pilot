# tests/test_pipeline.py
from odoo_pilot.pipeline import Pipeline
from odoo_pilot.config import Settings


def test_pipeline_import():
    """Verify pipeline can be instantiated."""
    settings = Settings(dry_run=True)
    p = Pipeline(settings)
    assert p.settings.dry_run is True
