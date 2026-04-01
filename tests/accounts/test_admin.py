import pytest
from django.urls import reverse

from tests.factories import AdminFactory, ApartmentFactory, InspectorFactory, SubscriptionFactory, UserFactory


@pytest.mark.django_db
class TestUserAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:accounts_user_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_changelist_displays_role(self, client):
        client.force_login(self.superuser)
        UserFactory(username="testowner")
        url = reverse("admin:accounts_user_changelist")
        response = client.get(url)
        assert response.status_code == 200
        assert "testowner" in response.content.decode()

    def test_change_form_loads(self, client):
        client.force_login(self.superuser)
        user = UserFactory()
        url = reverse("admin:accounts_user_change", args=[user.pk])
        response = client.get(url)
        assert response.status_code == 200

    def test_search_by_email(self, client):
        client.force_login(self.superuser)
        UserFactory(email="findme@example.com")
        url = reverse("admin:accounts_user_changelist")
        response = client.get(url, {"q": "findme@example.com"})
        assert response.status_code == 200
        assert "findme@example.com" in response.content.decode()

    def test_filter_by_role(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:accounts_user_changelist")
        response = client.get(url, {"role": "inspector"})
        assert response.status_code == 200

    def test_apartment_count_for_owner(self, client):
        client.force_login(self.superuser)
        owner = UserFactory()
        ApartmentFactory(owner=owner)
        ApartmentFactory(owner=owner)
        url = reverse("admin:accounts_user_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_apartment_count_for_inspector_is_zero(self):
        from apps.accounts.admin import UserAdmin

        inspector = InspectorFactory()
        admin_instance = UserAdmin(model=inspector.__class__, admin_site=None)
        assert admin_instance.apartment_count(inspector) == 0

    def test_non_staff_user_cannot_access(self, client):
        regular_user = UserFactory()
        client.force_login(regular_user)
        url = reverse("admin:accounts_user_changelist")
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
class TestSubscriptionAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:accounts_subscription_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_changelist_shows_subscription(self, client):
        client.force_login(self.superuser)
        sub = SubscriptionFactory()
        url = reverse("admin:accounts_subscription_changelist")
        response = client.get(url)
        assert response.status_code == 200
        assert sub.owner.username in response.content.decode()

    def test_change_form_loads(self, client):
        client.force_login(self.superuser)
        sub = SubscriptionFactory()
        url = reverse("admin:accounts_subscription_change", args=[sub.pk])
        response = client.get(url)
        assert response.status_code == 200

    def test_filter_by_plan(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:accounts_subscription_changelist")
        response = client.get(url, {"plan": "basis"})
        assert response.status_code == 200

    def test_search_by_owner_email(self, client):
        client.force_login(self.superuser)
        owner = UserFactory(email="sub-owner@example.com")
        SubscriptionFactory(owner=owner)
        url = reverse("admin:accounts_subscription_changelist")
        response = client.get(url, {"q": "sub-owner@example.com"})
        assert response.status_code == 200
        assert "sub-owner@example.com" in response.content.decode()
