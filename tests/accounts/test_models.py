import datetime

import pytest
from django.db import IntegrityError

from apps.accounts.models import Subscription, User
from tests.factories import AdminFactory, InspectorFactory, OwnerFactory, SubscriptionFactory, UserFactory


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

    def test_admin_factory(self, db):
        admin = AdminFactory()
        assert admin.role == User.Role.ADMIN

    def test_default_role_is_owner(self, db):
        user = User.objects.create_user(username="newuser", password="test123")
        assert user.role == User.Role.OWNER

    def test_address_field(self, db):
        user = UserFactory(address="Stephansplatz 1, 1010 Wien")
        assert user.address == "Stephansplatz 1, 1010 Wien"

    def test_address_blank_by_default(self, db):
        user = UserFactory()
        assert user.address == ""

    def test_availability_field(self, db):
        schedule = {"monday": ["09:00-17:00"], "tuesday": ["09:00-17:00"]}
        inspector = InspectorFactory(availability=schedule)
        inspector.refresh_from_db()
        assert inspector.availability == schedule

    def test_availability_empty_by_default(self, db):
        inspector = InspectorFactory()
        assert inspector.availability == {}


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
        assert Subscription.Plan.STANDARD == "standard"
        assert Subscription.Plan.PREMIUM == "premium"

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

    def test_basis_plan_limit(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        assert sub.get_monthly_inspection_limit() == 2

    def test_standard_plan_limit(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.STANDARD)
        assert sub.get_monthly_inspection_limit() == 4

    def test_premium_plan_limit(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.PREMIUM)
        assert sub.get_monthly_inspection_limit() == 8

    def test_unknown_plan_defaults_to_2(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        # Simulate unknown plan value
        sub.plan = "unknown"
        assert sub.get_monthly_inspection_limit() == 2


class TestSubscriptionPricing:
    def test_get_monthly_price_basis(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        assert sub.get_monthly_price() == 89

    def test_get_monthly_price_standard(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.STANDARD)
        assert sub.get_monthly_price() == 149

    def test_get_monthly_price_premium(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.PREMIUM)
        assert sub.get_monthly_price() == 249

    def test_get_monthly_price_unknown_defaults(self, db):
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        sub.plan = "unknown"
        assert sub.get_monthly_price() == 89

    def test_get_next_billing_date_monthly(self, db):
        sub = SubscriptionFactory(started_at=datetime.date(2026, 1, 15))
        next_date = sub.get_next_billing_date()
        assert next_date is not None
        assert next_date > datetime.date.today()
        assert next_date.day == 15

    def test_get_next_billing_date_month_end(self, db):
        sub = SubscriptionFactory(started_at=datetime.date(2026, 1, 31))
        next_date = sub.get_next_billing_date()
        assert next_date is not None
        # Clamped to 28 for safety
        assert next_date.day == 28

    def test_get_next_billing_date_paused_returns_none(self, db):
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        assert sub.get_next_billing_date() is None

    def test_get_next_billing_date_cancelled_returns_none(self, db):
        sub = SubscriptionFactory(status=Subscription.Status.CANCELLED)
        assert sub.get_next_billing_date() is None

    def test_get_inspections_used_this_month(self, db):
        sub = SubscriptionFactory()
        assert sub.get_inspections_used_this_month() == 0

    def test_plan_prices_dict(self):
        assert Subscription.PLAN_PRICES[Subscription.Plan.BASIS] == 89
        assert Subscription.PLAN_PRICES[Subscription.Plan.STANDARD] == 149
        assert Subscription.PLAN_PRICES[Subscription.Plan.PREMIUM] == 249
