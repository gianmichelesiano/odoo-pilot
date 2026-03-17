# tests/test_odoo_writer.py
from unittest.mock import patch, MagicMock
from odoo_pilot.odoo_writer import OdooWriter
from odoo_pilot.config import Settings
from odoo_pilot.models import BusinessData, ContactInfo, MenuItem


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
