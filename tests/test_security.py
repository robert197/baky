"""Tests for security features: encrypted fields, signed URLs, and production settings."""

from unittest.mock import MagicMock

import pytest

from baky.storage import get_signed_url
from tests.factories import ApartmentFactory


class TestEncryptedAccessCode:
    """Test that access_code is encrypted at rest and readable when needed."""

    @pytest.mark.django_db
    def test_access_code_stored_and_retrieved(self):
        apt = ApartmentFactory(access_code="1234")
        apt.refresh_from_db()
        assert apt.access_code == "1234"

    @pytest.mark.django_db
    def test_access_code_blank_allowed(self):
        apt = ApartmentFactory(access_code="")
        apt.refresh_from_db()
        assert apt.access_code == ""

    @pytest.mark.django_db
    def test_access_code_with_special_characters(self):
        apt = ApartmentFactory(access_code="PIN: 4567#")
        apt.refresh_from_db()
        assert apt.access_code == "PIN: 4567#"

    @pytest.mark.django_db
    def test_access_code_with_german_characters(self):
        apt = ApartmentFactory(access_code="Schlüssel-42ß")
        apt.refresh_from_db()
        assert apt.access_code == "Schlüssel-42ß"

    @pytest.mark.django_db
    def test_access_code_encrypted_in_database(self):
        """Verify the raw database value is NOT the plaintext."""
        apt = ApartmentFactory(access_code="secret-pin-999")
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_code FROM apartments_apartment WHERE id = %s",
                [apt.pk],
            )
            raw_value = cursor.fetchone()[0]
        # The raw value should not be the plaintext
        assert raw_value != "secret-pin-999"
        # But decryption via the model should work
        apt.refresh_from_db()
        assert apt.access_code == "secret-pin-999"

    @pytest.mark.django_db
    def test_access_notes_still_encrypted(self):
        """Existing encrypted field (access_notes) should still work."""
        apt = ApartmentFactory(access_notes="Portier anrufen: +43 1 234 5678")
        apt.refresh_from_db()
        assert apt.access_notes == "Portier anrufen: +43 1 234 5678"

    @pytest.mark.django_db
    def test_both_encrypted_fields_independent(self):
        apt = ApartmentFactory(
            access_code="7890",
            access_notes="Code für Haustür: 1111",
        )
        apt.refresh_from_db()
        assert apt.access_code == "7890"
        assert apt.access_notes == "Code für Haustür: 1111"


class TestPhotoSignedUrls:
    """Test that photo URLs use signed URL generation."""

    @pytest.mark.django_db
    def test_get_file_url_returns_url(self, photo):
        url = photo.get_file_url()
        assert url is not None
        assert "photos/" in url

    @pytest.mark.django_db
    def test_get_thumbnail_url_returns_url(self, photo):
        url = photo.get_thumbnail_url()
        assert url is not None

    @pytest.mark.django_db
    def test_get_file_url_custom_expiry(self, photo):
        url = photo.get_file_url(expiry=3600)
        assert url is not None

    @pytest.mark.django_db
    def test_get_file_url_no_file(self, db):
        """Photo without file returns None."""
        result = get_signed_url(None)
        assert result is None

    @pytest.mark.django_db
    def test_signed_url_with_s3_storage(self):
        """When S3 storage is used, signed URL uses querystring_auth."""
        mock_storage = MagicMock()
        mock_storage.querystring_auth = True
        mock_storage.url.return_value = "https://bucket.s3.amazonaws.com/photos/test.jpg?Signature=abc"

        mock_field = MagicMock()
        mock_field.__bool__ = lambda self: True
        mock_field.storage = mock_storage
        mock_field.name = "photos/test.jpg"

        url = get_signed_url(mock_field, expiry=86400)
        assert url is not None
        mock_storage.url.assert_called_once_with("photos/test.jpg", expire=86400)

    @pytest.mark.django_db
    def test_signed_url_default_expiry_24h(self):
        """Default expiry is 24 hours (86400 seconds)."""
        mock_storage = MagicMock()
        mock_storage.querystring_auth = True
        mock_storage.url.return_value = "https://example.com/signed"

        mock_field = MagicMock()
        mock_field.__bool__ = lambda self: True
        mock_field.storage = mock_storage
        mock_field.name = "photos/test.jpg"

        get_signed_url(mock_field)
        mock_storage.url.assert_called_once_with("photos/test.jpg", expire=86400)

    @pytest.mark.django_db
    def test_local_storage_returns_regular_url(self, photo):
        """In dev (local filesystem), returns regular URL without signature."""
        url = photo.get_file_url()
        assert url is not None


class TestProductionSecuritySettings:
    """Test that production security settings are correctly configured."""

    def test_production_has_hsts(self):
        """Production settings include HSTS headers."""
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "SECURE_SSL_REDIRECT = True" in content
        assert "SECURE_HSTS_SECONDS = 31536000" in content
        assert "SECURE_HSTS_INCLUDE_SUBDOMAINS = True" in content
        assert "SECURE_HSTS_PRELOAD = True" in content

    def test_production_has_secure_cookies(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "SESSION_COOKIE_SECURE = True" in content
        assert "CSRF_COOKIE_SECURE = True" in content

    def test_production_has_content_type_nosniff(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "SECURE_CONTENT_TYPE_NOSNIFF = True" in content

    def test_production_has_xss_filter(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "SECURE_BROWSER_XSS_FILTER = True" in content

    def test_production_has_proxy_ssl_header(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "SECURE_PROXY_SSL_HEADER" in content

    def test_production_has_s3_querystring_auth(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "AWS_QUERYSTRING_AUTH = True" in content
        assert "AWS_QUERYSTRING_EXPIRE = 86400" in content

    def test_production_has_private_acl(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert "AWS_DEFAULT_ACL = None" in content

    def test_production_has_field_encryption_key(self):
        from pathlib import Path

        prod_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "production.py"
        content = prod_file.read_text()
        assert 'FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")' in content

    def test_local_dev_has_no_ssl_redirect(self):
        from pathlib import Path

        local_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "local.py"
        content = local_file.read_text()
        assert "SECURE_SSL_REDIRECT" not in content

    def test_local_dev_has_encryption_key_default(self):
        from pathlib import Path

        local_file = Path(__file__).resolve().parent.parent / "baky" / "settings" / "local.py"
        content = local_file.read_text()
        assert "FIELD_ENCRYPTION_KEY" in content
        assert "default=" in content


class TestDeployCheck:
    """Verify manage.py check works in dev mode."""

    @pytest.mark.django_db
    def test_system_check_passes(self):
        """Django system checks pass in dev mode."""
        from django.core.management import call_command

        call_command("check")
