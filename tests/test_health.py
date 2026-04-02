import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_returns_200(self, client: Client):
        response = client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_json_content_type(self, client: Client):
        response = client.get("/health/")
        assert response["Content-Type"] == "application/json"

    def test_health_no_auth_required(self, client: Client):
        """Health check must work without authentication."""
        response = client.get("/health/")
        assert response.status_code == 200

    def test_health_includes_version(self, client: Client):
        response = client.get("/health/")
        data = response.json()
        assert "version" in data
        assert data["version"]  # not empty

    def test_health_get_only(self, client: Client):
        response = client.post("/health/")
        assert response.status_code == 405
