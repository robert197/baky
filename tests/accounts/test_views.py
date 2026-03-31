import pytest
from django.core import mail
from django.test import Client

from tests.factories import AdminFactory, InspectorFactory, UserFactory


@pytest.fixture
def client():
    return Client()


class TestLoginView:
    def test_get_login_page(self, client, db):
        response = client.get("/accounts/login/")
        assert response.status_code == 200
        assert "Anmelden" in response.content.decode()

    def test_login_with_valid_credentials(self, client, db):
        UserFactory(username="testowner", password="testpass123")
        response = client.post("/accounts/login/", {"username": "testowner", "password": "testpass123"})
        assert response.status_code == 302
        assert "/accounts/redirect/" in response.url

    def test_login_with_invalid_credentials(self, client, db):
        UserFactory(username="testowner", password="testpass123")
        response = client.post("/accounts/login/", {"username": "testowner", "password": "wrongpass"})
        assert response.status_code == 200
        assert "falsch" in response.content.decode()

    def test_login_with_next_parameter(self, client, db):
        UserFactory(username="testowner", password="testpass123")
        response = client.post(
            "/accounts/login/?next=/dashboard/", {"username": "testowner", "password": "testpass123"}
        )
        assert response.status_code == 302
        assert "/dashboard/" in response.url

    def test_authenticated_user_redirected_away_from_login(self, client, db):
        user = UserFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/accounts/login/")
        assert response.status_code == 302


class TestLogoutView:
    def test_logout_redirects_to_home(self, client, db):
        user = UserFactory(password="testpass123")
        client.force_login(user)
        response = client.post("/accounts/logout/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_logout_clears_session(self, client, db):
        user = UserFactory(password="testpass123")
        client.force_login(user)
        client.post("/accounts/logout/")
        response = client.get("/dashboard/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


class TestLoginRedirect:
    def test_owner_redirects_to_dashboard(self, client, db):
        user = UserFactory(role="owner", password="testpass123")
        client.force_login(user)
        response = client.get("/accounts/redirect/")
        assert response.status_code == 302
        assert "/dashboard/" in response.url

    def test_inspector_redirects_to_inspector_app(self, client, db):
        user = InspectorFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/accounts/redirect/")
        assert response.status_code == 302
        assert "/inspector/" in response.url

    def test_admin_redirects_to_admin(self, client, db):
        user = AdminFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/accounts/redirect/")
        assert response.status_code == 302
        assert "/admin/" in response.url

    def test_unauthenticated_redirects_to_login(self, client, db):
        response = client.get("/accounts/redirect/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


class TestPasswordReset:
    def test_get_password_reset_page(self, client, db):
        response = client.get("/accounts/password-reset/")
        assert response.status_code == 200
        assert "zurücksetzen" in response.content.decode().lower()

    def test_password_reset_sends_email(self, client, db):
        UserFactory(email="test@example.com")
        response = client.post("/accounts/password-reset/", {"email": "test@example.com"})
        assert response.status_code == 302
        assert len(mail.outbox) == 1
        assert "BAKY" in mail.outbox[0].subject

    def test_password_reset_with_nonexistent_email_still_redirects(self, client, db):
        """Should not reveal whether email exists."""
        response = client.post("/accounts/password-reset/", {"email": "nobody@example.com"})
        assert response.status_code == 302
        assert len(mail.outbox) == 0

    def test_password_reset_done_page(self, client, db):
        response = client.get("/accounts/password-reset/done/")
        assert response.status_code == 200
        assert "E-Mail gesendet" in response.content.decode()

    def test_password_reset_complete_page(self, client, db):
        response = client.get("/accounts/password-reset/complete/")
        assert response.status_code == 200
        assert "geändert" in response.content.decode()


class TestDashboardAccess:
    def test_owner_can_access_dashboard(self, client, db):
        user = UserFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/dashboard/")
        assert response.status_code == 200

    def test_inspector_cannot_access_dashboard(self, client, db):
        user = InspectorFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/dashboard/")
        assert response.status_code == 404

    def test_unauthenticated_redirected_from_dashboard(self, client, db):
        response = client.get("/dashboard/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


class TestInspectorAccess:
    def test_inspector_can_access_inspector_app(self, client, db):
        user = InspectorFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/inspector/")
        assert response.status_code == 200

    def test_owner_cannot_access_inspector_app(self, client, db):
        user = UserFactory(password="testpass123")
        client.force_login(user)
        response = client.get("/inspector/")
        assert response.status_code == 404

    def test_unauthenticated_redirected_from_inspector(self, client, db):
        response = client.get("/inspector/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
