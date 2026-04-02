import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Subscription
from tests.factories import ApartmentFactory, InspectorFactory, OwnerFactory, SubscriptionFactory


@pytest.mark.django_db
class TestSubscriptionOverview:
    def test_requires_login(self):
        client = Client()
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 302

    def test_requires_owner_role(self):
        client = Client()
        inspector = InspectorFactory()
        client.force_login(inspector)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 404

    def test_active_subscription(self):
        client = Client()
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Basis" in content

    def test_no_subscription(self):
        client = Client()
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Kein Abonnement" in content

    def test_paused_subscription(self):
        client = Client()
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        assert "Pausiert" in response.content.decode()

    def test_cancelled_subscription(self):
        client = Client()
        sub = SubscriptionFactory(status=Subscription.Status.CANCELLED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Gekündigt" in content


@pytest.mark.django_db
class TestPlanChangeRequest:
    def test_requires_login(self):
        client = Client()
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 302

    def test_get_shows_form(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 200

    def test_post_valid_sends_notification(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.post(
            reverse("dashboard:subscription_change"),
            {"requested_plan": "premium", "message": "Upgrade bitte"},
        )
        assert response.status_code == 302

    def test_no_subscription_redirects(self):
        client = Client()
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 302

    def test_paused_subscription_blocked(self):
        client = Client()
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestPauseRequest:
    def test_get_shows_form(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_pause"))
        assert response.status_code == 200

    def test_post_sends_notification(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.post(reverse("dashboard:subscription_pause"), {"reason": "Urlaub"})
        assert response.status_code == 302

    def test_already_paused_blocked(self):
        client = Client()
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_pause"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestCancelRequest:
    def test_get_shows_form(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_cancel"))
        assert response.status_code == 200

    def test_post_sends_notification(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.post(reverse("dashboard:subscription_cancel"), {})
        assert response.status_code == 302

    def test_already_cancelled_blocked(self):
        client = Client()
        sub = SubscriptionFactory(status=Subscription.Status.CANCELLED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_cancel"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestExtraInspectionBooking:
    def test_get_shows_form(self):
        client = Client()
        sub = SubscriptionFactory()
        ApartmentFactory(owner=sub.owner)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_extra"))
        assert response.status_code == 200

    def test_post_sends_notification(self):
        client = Client()
        sub = SubscriptionFactory()
        apartment = ApartmentFactory(owner=sub.owner)
        client.force_login(sub.owner)
        response = client.post(
            reverse("dashboard:subscription_extra"),
            {"apartment": apartment.pk, "preferred_date": "2026-04-15", "notes": "Dringend"},
        )
        assert response.status_code == 302

    def test_no_subscription_blocked(self):
        client = Client()
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:subscription_extra"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestBillingHistory:
    def test_requires_login(self):
        client = Client()
        response = client.get(reverse("dashboard:subscription_billing"))
        assert response.status_code == 302

    def test_shows_empty_state(self):
        client = Client()
        sub = SubscriptionFactory()
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_billing"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestDashboardIndexSubscriptionCard:
    def test_index_shows_subscription_card(self):
        client = Client()
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert "Basis" in response.content.decode()

    def test_index_no_subscription_shows_cta(self):
        client = Client()
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
