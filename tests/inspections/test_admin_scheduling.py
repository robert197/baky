"""Tests for the InspectionAdmin scheduling form validation."""

import datetime
import zoneinfo

import pytest
from django.utils import timezone

from apps.inspections.forms import InspectionAdminForm
from tests.factories import ApartmentFactory, InspectorFactory, OwnerFactory, SubscriptionFactory

VIENNA_TZ = zoneinfo.ZoneInfo("Europe/Vienna")


def _make_form_data(apartment, inspector, hour=10, days_ahead=1, **overrides):
    """Helper to create valid form data for InspectionAdminForm."""
    local_now = timezone.localtime(timezone.now())
    target_date = local_now.date() + datetime.timedelta(days=days_ahead)
    scheduled_at = datetime.datetime(target_date.year, target_date.month, target_date.day, hour, 0, 0, tzinfo=VIENNA_TZ)
    data = {
        "apartment": apartment.pk,
        "inspector": inspector.pk,
        "scheduled_at": scheduled_at,
        "scheduled_end": scheduled_at + datetime.timedelta(hours=2),
        "status": "scheduled",
        "overall_rating": "",
        "general_notes": "",
        "started_at": "",
        "completed_at": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestInspectionAdminForm:
    def test_valid_form(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        data = _make_form_data(apt, inspector)
        form = InspectionAdminForm(data=data)
        assert form.is_valid(), form.errors

    def test_form_rejects_outside_business_hours(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        data = _make_form_data(apt, inspector, hour=6)
        form = InspectionAdminForm(data=data)
        assert not form.is_valid()
        assert "scheduled_at" in form.errors

    def test_form_rejects_double_booking(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="extra")
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # Create first inspection via form
        data1 = _make_form_data(apt1, inspector, hour=10)
        form1 = InspectionAdminForm(data=data1)
        assert form1.is_valid(), form1.errors
        form1.save()

        # Overlapping inspection should be rejected
        data2 = _make_form_data(apt2, inspector, hour=11)
        form2 = InspectionAdminForm(data=data2)
        assert not form2.is_valid()
        assert "scheduled_at" in form2.errors

    def test_form_rejects_over_subscription_limit(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # Create 2 inspections (basis limit)
        for day in range(1, 3):
            data = _make_form_data(apt, inspector, hour=10, days_ahead=day)
            form = InspectionAdminForm(data=data)
            assert form.is_valid(), form.errors
            form.save()

        # Third should be rejected
        data3 = _make_form_data(apt, inspector, hour=10, days_ahead=3)
        form3 = InspectionAdminForm(data=data3)
        assert not form3.is_valid()
        assert "apartment" in form3.errors
