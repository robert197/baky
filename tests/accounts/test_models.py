import datetime

import pytest
from django.db import IntegrityError

from apps.accounts.models import Subscription, User
from tests.factories import InspectorFactory, OwnerFactory, SubscriptionFactory, UserFactory


class TestUserModel:
    def test_create_user(self, db):
        user = UserFactory()
        assert user.pk is not None
        assert user.role == User.Role.OWNER

    def test_owner_property(self, db):
        user = UserFactory()
        assert user.is_owner is True
        assert user.is_inspector is False

    def test_inspector_property(self, db):
        inspector = InspectorFactory()
        assert inspector.is_inspector is True
        assert inspector.is_owner is False

    def test_user_str(self, db):
        user = UserFactory(username="testuser")
        assert str(user) == "testuser (owner)"

    def test_user_str_with_full_name(self, db):
        user = UserFactory(username="testuser", first_name="Max", last_name="Müller")
        assert str(user) == "Max Müller (owner)"

    def test_phone_field(self, db):
        user = UserFactory(phone="+43 1 234 5678")
        assert user.phone == "+43 1 234 5678"

    def test_phone_blank_by_default(self, db):
        user = UserFactory()
        assert user.phone == ""

    def test_role_choices(self):
        assert User.Role.OWNER == "owner"
        assert User.Role.INSPECTOR == "inspector"
        assert User.Role.ADMIN == "admin"

    def test_default_role_is_owner(self, db):
        user = User.objects.create_user(username="newuser", password="test123")
        assert user.role == User.Role.OWNER


class TestSubscriptionModel:
    def test_create(self, subscription):
        assert subscription.pk is not None
        assert subscription.plan == Subscription.Plan.BASIS
        assert subscription.status == Subscription.Status.ACTIVE

    def test_str(self, subscription):
        result = str(subscription)
        assert subscription.owner.username in result
        assert "Basis" in result
        assert "Aktiv" in result

    def test_one_subscription_per_owner(self, db, user):
        SubscriptionFactory(owner=user)
        with pytest.raises(IntegrityError):
            SubscriptionFactory(owner=user)

    def test_plan_choices(self):
        assert Subscription.Plan.BASIS == "basis"
        assert Subscription.Plan.EXTRA == "extra"

    def test_status_choices(self):
        assert Subscription.Status.ACTIVE == "active"
        assert Subscription.Status.PAUSED == "paused"
        assert Subscription.Status.CANCELLED == "cancelled"

    def test_billing_cycle_choices(self):
        assert Subscription.BillingCycle.MONTHLY == "monthly"
        assert Subscription.BillingCycle.YEARLY == "yearly"

    def test_ordering(self, db):
        owner1 = OwnerFactory()
        owner2 = OwnerFactory()
        sub1 = SubscriptionFactory(owner=owner1, started_at=datetime.date(2024, 1, 1))
        sub2 = SubscriptionFactory(owner=owner2, started_at=datetime.date(2024, 6, 1))
        subs = list(Subscription.objects.all())
        assert subs[0] == sub2  # More recent first
        assert subs[1] == sub1

    def test_cascade_delete_owner(self, db, subscription):
        owner = subscription.owner
        owner.delete()
        assert Subscription.objects.filter(pk=subscription.pk).count() == 0

    def test_related_name(self, db, user):
        sub = SubscriptionFactory(owner=user)
        assert user.subscription == sub
