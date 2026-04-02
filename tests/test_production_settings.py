from django.conf import settings


class TestProductionReadySettings:
    def test_upload_max_size_sufficient_for_photos(self):
        """Upload limit must accommodate large HEIF photos from mobile."""
        assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE >= 10 * 1024 * 1024  # At least 10MB

    def test_file_upload_max_size_sufficient(self):
        assert settings.FILE_UPLOAD_MAX_MEMORY_SIZE >= 10 * 1024 * 1024

    def test_database_url_configured(self):
        """DATABASE_URL env var must produce a working database config."""
        assert settings.DATABASES["default"]["ENGINE"] != ""

    def test_static_root_configured(self):
        assert settings.STATIC_ROOT is not None
