"""Tests for inspection scheduling validation, subscription limits, and double-booking prevention."""

import datetime
import zoneinfo

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.inspections.models import BUSINESS_HOURS_END, BUSINESS_HOURS_START, Inspection
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
    SubscriptionFactory,
)

VIENNA_TZ = zoneinfo.ZoneInfo("Europe/Vienna")


def _make_scheduled_at(hour=10, days_ahead=1):
    """Create a scheduled_at datetime at the given local hour in Vienna timezone."""
    now = timezone.now()
    local_now = timezone.localtime(now)
    target_date = local_now.date() + datetime.timedelta(days=days_ahead)
    return datetime.datetime(target_date.year, target_date.month, target_date.day, hour, 0, 0, tzinfo=VIENNA_TZ)


def _make_owner_with_subscription(plan="standard"):
    """Create an owner with an active subscription."""
    owner = OwnerFactory()
    SubscriptionFactory(owner=owner, plan=plan)
    return owner


@pytest.mark.django_db
class TestBusinessHoursValidation:
    def test_valid_business_hours(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        inspection.clean()  # Should not raise

    def test_start_before_business_hours_rejected(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=6),
            scheduled_end=_make_scheduled_at(hour=8),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        assert "scheduled_at" in exc_info.value.message_dict

    def test_start_at_18_rejected(self):
        """Starting at 18:00 is outside business hours (8-18)."""
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=18),
            scheduled_end=_make_scheduled_at(hour=20),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        assert "scheduled_at" in exc_info.value.message_dict

    def test_end_after_business_hours_rejected(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=15),
            scheduled_end=_make_scheduled_at(hour=19),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        assert "scheduled_end" in exc_info.value.message_dict

    def test_start_at_8_accepted(self):
        """Starting at exactly 8:00 is valid."""
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=8),
            scheduled_end=_make_scheduled_at(hour=10),
        )
        inspection.clean()  # Should not raise

    def test_end_at_exactly_18_accepted(self):
        """Ending at exactly 18:00 is valid."""
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=16),
            scheduled_end=_make_scheduled_at(hour=18),
        )
        inspection.clean()  # Should not raise

    def test_business_hours_error_message_contains_times(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=5),
            scheduled_end=_make_scheduled_at(hour=7),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        msg = str(exc_info.value.message_dict["scheduled_at"])
        assert str(BUSINESS_HOURS_START) in msg
        assert str(BUSINESS_HOURS_END) in msg


@pytest.mark.django_db
class TestMinimumDurationValidation:
    def test_two_hour_window_accepted(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        inspection.clean()  # Should not raise

    def test_one_hour_window_rejected(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=11),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        assert "scheduled_end" in exc_info.value.message_dict
        assert "Mindestdauer" in str(exc_info.value.message_dict["scheduled_end"])

    def test_auto_sets_scheduled_end_if_blank(self):
        """scheduled_end should auto-populate to scheduled_at + 2 hours."""
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        scheduled_at = _make_scheduled_at(hour=10)
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=scheduled_at,
            scheduled_end=None,
        )
        inspection.clean()
        assert inspection.scheduled_end == scheduled_at + datetime.timedelta(hours=2)

    def test_three_hour_window_accepted(self):
        owner = _make_owner_with_subscription()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=13),
        )
        inspection.clean()  # Should not raise


@pytest.mark.django_db
class TestDoubleBookingValidation:
    def test_no_overlap_accepted(self):
        owner = _make_owner_with_subscription()
        inspector = InspectorFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        InspectionFactory(
            inspector=inspector,
            apartment=apt1,
            scheduled_at=_make_scheduled_at(hour=8),
            scheduled_end=_make_scheduled_at(hour=10),
        )
        # Non-overlapping inspection
        i2 = InspectionFactory.build(
            inspector=inspector,
            apartment=apt2,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        i2.clean()  # Should not raise

    def test_overlapping_inspections_rejected(self):
        owner = _make_owner_with_subscription()
        inspector = InspectorFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        InspectionFactory(
            inspector=inspector,
            apartment=apt1,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        i2 = InspectionFactory.build(
            inspector=inspector,
            apartment=apt2,
            scheduled_at=_make_scheduled_at(hour=11),
            scheduled_end=_make_scheduled_at(hour=13),
        )
        with pytest.raises(ValidationError) as exc_info:
            i2.clean()
        assert "scheduled_at" in exc_info.value.message_dict
        assert "bereits eine Inspektion" in str(exc_info.value.message_dict["scheduled_at"])

    def test_different_inspector_not_conflicting(self):
        """Two different inspectors can have overlapping schedules."""
        owner = _make_owner_with_subscription()
        inspector1 = InspectorFactory()
        inspector2 = InspectorFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        InspectionFactory(
            inspector=inspector1,
            apartment=apt1,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        i2 = InspectionFactory.build(
            inspector=inspector2,
            apartment=apt2,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        i2.clean()  # Should not raise

    def test_cancelled_inspection_not_conflicting(self):
        """Cancelled inspections don't block scheduling."""
        owner = _make_owner_with_subscription()
        inspector = InspectorFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        InspectionFactory(
            inspector=inspector,
            apartment=apt1,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
            status=Inspection.Status.CANCELLED,
        )
        i2 = InspectionFactory.build(
            inspector=inspector,
            apartment=apt2,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        i2.clean()  # Should not raise

    def test_editing_existing_inspection_not_self_conflicting(self):
        """Editing an existing inspection should not conflict with itself."""
        owner = _make_owner_with_subscription()
        inspector = InspectorFactory()
        apt = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        # Update the same inspection — should not conflict with itself
        inspection.scheduled_end = _make_scheduled_at(hour=13)
        inspection.clean()  # Should not raise


@pytest.mark.django_db
class TestSubscriptionLimitValidation:
    def test_basis_plan_allows_2_per_month(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # First inspection
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=8),
            scheduled_end=_make_scheduled_at(hour=10),
        )
        # Second inspection
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        # Third — should be rejected
        i3 = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=14),
            scheduled_end=_make_scheduled_at(hour=16),
        )
        with pytest.raises(ValidationError) as exc_info:
            i3.clean()
        assert "apartment" in exc_info.value.message_dict
        assert "Inspektionslimit" in str(exc_info.value.message_dict["apartment"])

    def test_standard_plan_allows_4_per_month(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # Create 4 inspections on different days within the same month
        for day_offset in range(1, 5):
            InspectionFactory(
                apartment=apt,
                inspector=inspector,
                scheduled_at=_make_scheduled_at(hour=10, days_ahead=day_offset),
                scheduled_end=_make_scheduled_at(hour=12, days_ahead=day_offset),
            )

        # Fifth should be rejected
        i5 = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=14, days_ahead=5),
            scheduled_end=_make_scheduled_at(hour=16, days_ahead=5),
        )
        with pytest.raises(ValidationError) as exc_info:
            i5.clean()
        assert "apartment" in exc_info.value.message_dict

    def test_premium_plan_allows_8_per_month(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="premium")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # Create 8 inspections on different days
        for day_offset in range(1, 9):
            InspectionFactory(
                apartment=apt,
                inspector=inspector,
                scheduled_at=_make_scheduled_at(hour=10, days_ahead=day_offset),
                scheduled_end=_make_scheduled_at(hour=12, days_ahead=day_offset),
            )

        # Ninth should be rejected
        i9 = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=14, days_ahead=9),
            scheduled_end=_make_scheduled_at(hour=16, days_ahead=9),
        )
        with pytest.raises(ValidationError) as exc_info:
            i9.clean()
        assert "apartment" in exc_info.value.message_dict

    def test_no_subscription_rejected(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        assert "apartment" in exc_info.value.message_dict
        assert "Abonnement" in str(exc_info.value.message_dict["apartment"])

    def test_paused_subscription_rejected(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis", status="paused")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        inspection = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection.clean()
        assert "apartment" in exc_info.value.message_dict
        assert "nicht aktiv" in str(exc_info.value.message_dict["apartment"])

    def test_cancelled_inspections_dont_count_toward_limit(self):
        """Cancelled inspections should not count toward the monthly limit."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # Two cancelled inspections
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=8),
            scheduled_end=_make_scheduled_at(hour=10),
            status=Inspection.Status.CANCELLED,
        )
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
            status=Inspection.Status.CANCELLED,
        )

        # Two new scheduled inspections should be allowed
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=8, days_ahead=2),
            scheduled_end=_make_scheduled_at(hour=10, days_ahead=2),
        )
        i4 = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10, days_ahead=2),
            scheduled_end=_make_scheduled_at(hour=12, days_ahead=2),
        )
        i4.clean()  # Should not raise — cancelled ones don't count

    def test_limit_error_message_shows_plan(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=8),
            scheduled_end=_make_scheduled_at(hour=10),
        )
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=10),
            scheduled_end=_make_scheduled_at(hour=12),
        )
        i3 = InspectionFactory.build(
            apartment=apt,
            inspector=inspector,
            scheduled_at=_make_scheduled_at(hour=14),
            scheduled_end=_make_scheduled_at(hour=16),
        )
        with pytest.raises(ValidationError) as exc_info:
            i3.clean()
        msg = str(exc_info.value.message_dict["apartment"])
        assert "Basis" in msg
        assert "2/2" in msg
