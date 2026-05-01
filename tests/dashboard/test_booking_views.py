"""Tests for owner booking calendar and slot booking views."""

import datetime
import zoneinfo

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from apps.inspections.models import Inspection
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
    SubscriptionFactory,
)

VIENNA_TZ = zoneinfo.ZoneInfo("Europe/Vienna")


def _future_date(days_ahead=3):
    """Return a date N days from now."""
    return datetime.date.today() + datetime.timedelta(days=days_ahead)


@pytest.mark.django_db
class TestBookingCalendarView:
    def test_requires_login(self):
        client = Client()
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_requires_owner_role(self):
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 404

    def test_requires_active_subscription(self):
        owner = OwnerFactory()
        ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 302
        assert "subscription" in resp.url

    def test_requires_apartments(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 302

    def test_renders_successfully(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"), {"apartment": apt.pk})
        assert resp.status_code == 200
        assert "Termin buchen" in resp.content.decode()

    def test_shows_apartment_selector(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        ApartmentFactory(owner=owner, address="Teststraße 1, 1010 Wien")
        ApartmentFactory(owner=owner, address="Teststraße 2, 1020 Wien")
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"))
        content = resp.content.decode()
        assert "Teststraße 1" in content
        assert "Teststraße 2" in content

    def test_auto_selects_single_apartment(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 200
        # Should auto-select the single apartment and show calendar
        assert resp.context["selected_apartment"] == apt

    def test_week_navigation_htmx(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(
            reverse("dashboard:booking_calendar"),
            {"apartment": apt.pk, "week": 1},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        # HTMX request returns partial template (no full page wrapper)
        assert "base_dashboard" not in resp.content.decode()
        assert "Wohnung auswählen" not in resp.content.decode()

    def test_no_past_weeks(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"), {"apartment": apt.pk, "week": -5})
        assert resp.status_code == 200
        assert resp.context["week_offset"] == 0

    def test_duplicate_week_params_use_requested_navigation_week(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(f"{reverse('dashboard:booking_calendar')}?apartment={apt.pk}&week=1&week=0")
        assert resp.status_code == 200
        assert resp.context["week_offset"] == 1

    def test_shows_subscription_usage(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis")
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"), {"apartment": apt.pk})
        content = resp.content.decode()
        assert "0/2" in content  # 0 used out of 2 on basis plan

    def test_paused_subscription_redirects(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, status="paused")
        ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 302

    def test_excludes_paused_apartments(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        ApartmentFactory(owner=owner, status="paused")
        client = Client()
        client.force_login(owner)
        # No active apartments → redirects
        resp = client.get(reverse("dashboard:booking_calendar"))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestBookSlotView:
    def test_creates_inspection(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)

        target_date = _future_date(days_ahead=5)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        assert "Termin gebucht" in resp.content.decode()

        inspection = Inspection.objects.get(apartment=apt)
        assert inspection.status == Inspection.Status.SCHEDULED
        assert inspection.inspector is None
        assert inspection.time_slot == "morning"
        local_start = inspection.scheduled_at.astimezone(VIENNA_TZ)
        local_end = inspection.scheduled_end.astimezone(VIENNA_TZ)
        assert local_start.hour == 8
        assert local_start.minute == 0
        assert local_end.hour == 10
        assert local_end.minute == 30

    def test_requires_post(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:book_slot"))
        assert resp.status_code == 405

    def test_requires_owner(self):
        client = Client()
        resp = client.post(reverse("dashboard:book_slot"))
        assert resp.status_code == 302

    def test_requires_active_subscription(self):
        owner = OwnerFactory()
        ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": 1, "date": "2026-05-01", "slot": "morning"},
        )
        assert resp.status_code == 200
        assert "Abonnement" in resp.content.decode()

    def test_rejects_invalid_slot(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": _future_date().isoformat(), "slot": "invalid"},
        )
        assert resp.status_code == 200
        assert "Ungültiger Zeitslot" in resp.content.decode()

    def test_rejects_past_date(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": yesterday, "slot": "morning"},
        )
        assert resp.status_code == 200
        assert "24 Stunden" in resp.content.decode()

    def test_rejects_same_apartment_same_day(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        # Existing inspection
        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
        )

        client = Client()
        client.force_login(owner)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "afternoon"},
        )
        assert resp.status_code == 200
        assert "bereits eine Inspektion" in resp.content.decode()

    def test_rejects_over_subscription_limit(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="basis")  # 2/month limit
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()

        # Create 2 existing inspections on different days
        for day_offset in [3, 4]:
            d = _future_date(days_ahead=day_offset)
            InspectionFactory(
                apartment=apt,
                inspector=inspector,
                scheduled_at=datetime.datetime(d.year, d.month, d.day, 8, 0, tzinfo=VIENNA_TZ),
                scheduled_end=datetime.datetime(d.year, d.month, d.day, 10, 30, tzinfo=VIENNA_TZ),
            )

        client = Client()
        client.force_login(owner)
        target_date = _future_date(days_ahead=5)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        assert "Inspektionslimit" in resp.content.decode()

    def test_sets_time_slot_field(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        target_date = _future_date(days_ahead=5)

        client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "afternoon"},
        )
        inspection = Inspection.objects.get(apartment=apt)
        assert inspection.time_slot == "afternoon"
        local_start = inspection.scheduled_at.astimezone(VIENNA_TZ)
        assert local_start.hour == 13
        assert local_start.minute == 30

    def test_scopes_to_owner_apartments(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)

        client = Client()
        client.force_login(owner)
        target_date = _future_date(days_ahead=5)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": other_apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 404

    def test_midday_slot_times(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        target_date = _future_date(days_ahead=5)

        client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "midday"},
        )
        inspection = Inspection.objects.get(apartment=apt)
        assert inspection.time_slot == "midday"
        local_start = inspection.scheduled_at.astimezone(VIENNA_TZ)
        local_end = inspection.scheduled_end.astimezone(VIENNA_TZ)
        assert local_start.hour == 10
        assert local_start.minute == 30
        assert local_end.hour == 13
        assert local_end.minute == 0

    def test_different_apartment_same_slot_rejected(self):
        """Global slot exclusivity: same date+slot across apartments is rejected."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")  # 4/month
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        # Book apt1 morning slot
        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
        )

        client = Client()
        client.force_login(owner)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt2.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        assert "bereits vergeben" in resp.content.decode()
        assert Inspection.objects.filter(apartment=apt2).count() == 0

    def test_different_apartment_different_slot_accepted(self):
        """Different slots on the same day for different apartments are OK."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")  # 4/month
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        # Book apt1 morning slot
        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
        )

        client = Client()
        client.force_login(owner)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt2.pk, "date": target_date.isoformat(), "slot": "afternoon"},
        )
        assert resp.status_code == 200
        assert "Termin gebucht" in resp.content.decode()

    def test_cross_owner_same_slot_rejected(self):
        """Owner B cannot book a slot already booked by Owner A."""
        owner_a = OwnerFactory()
        owner_b = OwnerFactory()
        SubscriptionFactory(owner=owner_a, plan="standard")
        SubscriptionFactory(owner=owner_b, plan="standard")
        apt_a = ApartmentFactory(owner=owner_a)
        apt_b = ApartmentFactory(owner=owner_b)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        # Owner A books morning slot
        InspectionFactory(
            apartment=apt_a,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
        )

        # Owner B tries to book the same slot
        client = Client()
        client.force_login(owner_b)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt_b.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        assert "bereits vergeben" in resp.content.decode()
        assert Inspection.objects.filter(apartment=apt_b).count() == 0


@pytest.mark.django_db
class TestBookingNotification:
    def test_booking_queues_notification(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        target_date = _future_date(days_ahead=5)

        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        # Inspection was created
        assert Inspection.objects.filter(apartment=apt, status=Inspection.Status.SCHEDULED).exists()


@pytest.mark.django_db
class TestBookingFormValidation:
    def test_booking_form_filters_active_apartments(self):
        from apps.dashboard.forms import BookingApartmentForm

        owner = OwnerFactory()
        active_apt = ApartmentFactory(owner=owner, status="active")
        ApartmentFactory(owner=owner, status="paused")
        ApartmentFactory(owner=owner, status="archived")

        form = BookingApartmentForm(owner=owner)
        qs = form.fields["apartment"].queryset
        assert list(qs) == [active_apt]

    def test_booking_form_excludes_other_owners(self):
        from apps.dashboard.forms import BookingApartmentForm

        owner = OwnerFactory()
        other_owner = OwnerFactory()
        my_apt = ApartmentFactory(owner=owner)
        ApartmentFactory(owner=other_owner)

        form = BookingApartmentForm(owner=owner)
        qs = form.fields["apartment"].queryset
        assert list(qs) == [my_apt]


@pytest.mark.django_db
class TestInspectionWithoutInspector:
    def test_inspection_without_inspector_valid(self):
        """Inspections can be created without an inspector (owner-booked)."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=5)

        inspection = Inspection(
            apartment=apt,
            inspector=None,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
            status=Inspection.Status.SCHEDULED,
        )
        inspection.full_clean()
        inspection.save()
        assert inspection.pk is not None
        assert inspection.inspector is None

    def test_str_without_inspector(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=5)

        inspection = Inspection(
            apartment=apt,
            inspector=None,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
        )
        inspection.full_clean()
        inspection.save()
        assert "Geplant" in str(inspection)


@pytest.mark.django_db
class TestSameDayDuplicateValidation:
    def test_same_apartment_same_day_rejected(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
        )

        inspection2 = Inspection(
            apartment=apt,
            inspector=None,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 13, 30, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 16, 0, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
        )

        with pytest.raises(Exception) as exc_info:
            inspection2.full_clean()
        assert "bereits eine Inspektion" in str(exc_info.value)

    def test_same_apartment_different_day_accepted(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        day1 = _future_date(days_ahead=5)
        day2 = _future_date(days_ahead=6)

        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=datetime.datetime(day1.year, day1.month, day1.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(day1.year, day1.month, day1.day, 10, 30, tzinfo=VIENNA_TZ),
        )

        inspection2 = Inspection(
            apartment=apt,
            inspector=None,
            scheduled_at=datetime.datetime(day2.year, day2.month, day2.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(day2.year, day2.month, day2.day, 10, 30, tzinfo=VIENNA_TZ),
            status=Inspection.Status.SCHEDULED,
        )
        inspection2.full_clean()  # Should not raise

    def test_different_apartment_same_slot_rejected(self):
        """Global slot exclusivity at model level: same date+slot is rejected."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
        )

        inspection2 = Inspection(
            apartment=apt2,
            inspector=None,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
            status=Inspection.Status.SCHEDULED,
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection2.full_clean()
        assert "bereits vergeben" in str(exc_info.value)

    def test_different_apartment_different_slot_accepted(self):
        """Different slots on same day for different apartments are fine."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot="morning",
        )

        inspection2 = Inspection(
            apartment=apt2,
            inspector=None,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 13, 30, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 16, 0, tzinfo=VIENNA_TZ
            ),
            time_slot="afternoon",
            status=Inspection.Status.SCHEDULED,
        )
        inspection2.full_clean()  # Should not raise


@pytest.mark.django_db
class TestSubscriptionUsageCounting:
    def test_counts_scheduled_inspections(self):
        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=3)

        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
        )

        assert sub.get_inspections_used_this_month() == 1

    def test_excludes_cancelled_inspections(self):
        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=3)

        InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.CANCELLED,
        )

        assert sub.get_inspections_used_this_month() == 0


@pytest.mark.django_db
class TestLateCancellationQuotaCounting:
    def test_late_cancelled_counts_as_used(self):
        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=3)

        InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.CANCELLED,
            late_cancellation=True,
        )

        assert sub.get_inspections_used_this_month() == 1

    def test_early_cancelled_not_counted(self):
        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=3)

        InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.CANCELLED,
            late_cancellation=False,
        )

        assert sub.get_inspections_used_this_month() == 0


@pytest.mark.django_db
class TestCancelBookingView:
    def _cancel_url(self, inspection_pk):
        return reverse("dashboard:cancel_booking", args=[inspection_pk])

    def _create_inspection(self, owner, days_ahead=5):
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=days_ahead)
        return InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
            time_slot=Inspection.TimeSlot.MORNING,
        )

    def test_cancel_scheduled_inspection_timely(self):
        """>=24h before: status=CANCELLED, late_cancellation=False."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner, days_ahead=5)
        client = Client()
        client.force_login(owner)

        resp = client.post(self._cancel_url(inspection.pk))

        assert resp.status_code == 200
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.CANCELLED
        assert inspection.late_cancellation is False
        assert inspection.cancelled_at is not None

    def test_cancel_scheduled_inspection_late(self):
        """<24h before: status=CANCELLED, late_cancellation=True."""
        from unittest.mock import patch

        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=1)
        inspection = InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
            time_slot=Inspection.TimeSlot.MORNING,
        )
        # Mock timezone.now() to be <24h before the slot
        fake_now = inspection.scheduled_at - datetime.timedelta(hours=12)
        client = Client()
        client.force_login(owner)

        with patch("apps.dashboard.views.timezone.now", return_value=fake_now):
            resp = client.post(self._cancel_url(inspection.pk))

        assert resp.status_code == 200
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.CANCELLED
        assert inspection.late_cancellation is True

    def test_cancel_sets_cancelled_at(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        client = Client()
        client.force_login(owner)

        client.post(self._cancel_url(inspection.pk))

        inspection.refresh_from_db()
        assert inspection.cancelled_at is not None

    def test_cannot_cancel_completed_inspection(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        inspection.status = Inspection.Status.COMPLETED
        inspection.save(update_fields=["status"])
        client = Client()
        client.force_login(owner)

        resp = client.post(self._cancel_url(inspection.pk))
        assert resp.status_code == 404

    def test_cannot_cancel_in_progress_inspection(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        inspection.status = Inspection.Status.IN_PROGRESS
        inspection.save(update_fields=["status"])
        client = Client()
        client.force_login(owner)

        resp = client.post(self._cancel_url(inspection.pk))
        assert resp.status_code == 404

    def test_cannot_cancel_other_owners_inspection(self):
        owner1 = OwnerFactory()
        owner2 = OwnerFactory()
        SubscriptionFactory(owner=owner1)
        SubscriptionFactory(owner=owner2)
        inspection = self._create_inspection(owner1)
        client = Client()
        client.force_login(owner2)

        resp = client.post(self._cancel_url(inspection.pk))
        assert resp.status_code == 404

    def test_unauthenticated_redirects_to_login(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        client = Client()

        resp = client.post(self._cancel_url(inspection.pk))
        assert resp.status_code == 302
        assert "/login/" in resp.url

    def test_inspector_cannot_cancel(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)

        resp = client.post(self._cancel_url(inspection.pk))
        assert resp.status_code == 404

    def test_get_not_allowed(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        client = Client()
        client.force_login(owner)

        resp = client.get(self._cancel_url(inspection.pk))
        assert resp.status_code == 405

    def test_double_cancel_returns_404(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        inspection.status = Inspection.Status.CANCELLED
        inspection.save(update_fields=["status"])
        client = Client()
        client.force_login(owner)

        resp = client.post(self._cancel_url(inspection.pk))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestCancellationNotification:
    def test_cancellation_sends_admin_email(self):
        """send_cancellation_notification sends email to admin."""
        from django.core import mail

        from apps.dashboard.tasks import send_cancellation_notification

        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=5)
        inspection = InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.CANCELLED,
            late_cancellation=False,
            time_slot=Inspection.TimeSlot.MORNING,
        )

        send_cancellation_notification(owner.pk, inspection.pk)

        assert len(mail.outbox) == 1
        assert "Stornierung" in mail.outbox[0].subject
        assert apt.address in mail.outbox[0].subject


@pytest.mark.django_db
class TestUpcomingInspectionsDisplay:
    def test_shows_scheduled_inspections_on_calendar_page(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=5)
        InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
            time_slot=Inspection.TimeSlot.MORNING,
        )
        client = Client()
        client.force_login(owner)

        resp = client.get(reverse("dashboard:booking_calendar"))
        content = resp.content.decode()

        assert resp.status_code == 200
        assert "Anstehende Termine" in content
        assert apt.address in content

    def test_hides_completed_inspections(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=5)
        InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.COMPLETED,
            time_slot=Inspection.TimeSlot.MORNING,
        )
        client = Client()
        client.force_login(owner)

        resp = client.get(reverse("dashboard:booking_calendar"))
        content = resp.content.decode()

        assert "Anstehende Termine" not in content

    def test_cancel_button_present(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=5)
        inspection = InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
            time_slot=Inspection.TimeSlot.MORNING,
        )
        client = Client()
        client.force_login(owner)

        resp = client.get(reverse("dashboard:booking_calendar"))
        content = resp.content.decode()

        assert "Stornieren" in content
        assert f"stornieren/{inspection.pk}/" in content

    def test_shows_cancellation_policy_text(self):
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)

        resp = client.get(reverse("dashboard:booking_calendar"))
        content = resp.content.decode()

        assert "Stornierungen bis 24 Stunden" in content


@pytest.mark.django_db
class TestCancellationIntegration:
    def test_book_cancel_rebook_flow(self):
        """Owner books slot, cancels >=24h before, then rebooks same slot."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        target_date = _future_date(days_ahead=5)

        # Book
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        inspection = Inspection.objects.get(apartment=apt, status=Inspection.Status.SCHEDULED)

        # Cancel (timely)
        resp = client.post(reverse("dashboard:cancel_booking", args=[inspection.pk]))
        assert resp.status_code == 200
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.CANCELLED
        assert inspection.late_cancellation is False

        # Rebook same slot
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.status_code == 200
        new_inspection = Inspection.objects.filter(apartment=apt, status=Inspection.Status.SCHEDULED).first()
        assert new_inspection is not None
        assert new_inspection.pk != inspection.pk

    def test_late_cancel_prevents_overbooking(self):
        """Owner at limit, late-cancels, cannot book new (quota consumed)."""
        from unittest.mock import patch

        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="basis")  # 2/month limit
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)

        # Book 2 inspections (at limit)
        for days in [5, 6]:
            target_date = _future_date(days_ahead=days)
            client.post(
                reverse("dashboard:book_slot"),
                {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
            )
        assert sub.get_inspections_used_this_month() == 2

        # Late-cancel one
        inspection = (
            Inspection.objects.filter(apartment=apt, status=Inspection.Status.SCHEDULED)
            .order_by("scheduled_at")
            .first()
        )
        fake_now = inspection.scheduled_at - datetime.timedelta(hours=12)
        with patch("apps.dashboard.views.timezone.now", return_value=fake_now):
            client.post(reverse("dashboard:cancel_booking", args=[inspection.pk]))

        inspection.refresh_from_db()
        assert inspection.late_cancellation is True
        # Still at limit — late cancel consumed quota
        assert sub.get_inspections_used_this_month() == 2

    def test_early_cancel_allows_rebooking(self):
        """Owner at limit, early-cancels, can book new (quota restored)."""
        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="basis")  # 2/month limit
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)

        # Book 2 inspections (at limit)
        for days in [5, 6]:
            target_date = _future_date(days_ahead=days)
            client.post(
                reverse("dashboard:book_slot"),
                {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
            )
        assert sub.get_inspections_used_this_month() == 2

        # Early-cancel one (>=24h before, default behavior with days_ahead=5)
        inspection = (
            Inspection.objects.filter(apartment=apt, status=Inspection.Status.SCHEDULED)
            .order_by("scheduled_at")
            .first()
        )
        client.post(reverse("dashboard:cancel_booking", args=[inspection.pk]))

        inspection.refresh_from_db()
        assert inspection.late_cancellation is False
        # Quota restored
        assert sub.get_inspections_used_this_month() == 1


@pytest.mark.django_db
class TestCalendarUXRedesign:
    """Tests for #84 — calendar booking UX redesign."""

    def _setup(self):
        owner = OwnerFactory()
        sub = SubscriptionFactory(owner=owner, plan="basis")
        apt = ApartmentFactory(owner=owner, address="Teststraße 10, 1010 Wien")
        client = Client()
        client.force_login(owner)
        url = reverse("dashboard:booking_calendar")
        return owner, sub, apt, client, url

    def test_legend_displayed_on_calendar(self):
        """Calendar page shows a visual legend explaining slot states."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        content = resp.content.decode()
        assert "Verfügbar" in content
        assert "Ihr Termin" in content
        assert "Vergeben" in content
        assert "Vergangen" in content

    def test_subscription_progress_bar_displayed(self):
        """Calendar shows a progress bar for subscription usage."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        content = resp.content.decode()
        assert 'role="progressbar"' in content
        assert "0/2" in content

    def test_subscription_progress_bar_color_at_limit(self):
        """Progress bar turns red when at subscription limit."""
        owner, sub, apt, client, url = self._setup()
        for days_ahead, slot in [(3, "morning"), (4, "midday")]:
            target_date = _future_date(days_ahead=days_ahead)
            client.post(
                reverse("dashboard:book_slot"),
                {"apartment": apt.pk, "date": target_date.isoformat(), "slot": slot},
            )
        resp = client.get(url, {"apartment": apt.pk})
        assert "bg-rose-500" in resp.content.decode()

    def test_booking_hint_displayed(self):
        """Calendar page shows a booking hint for users."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        assert "Wählen Sie einen" in resp.content.decode()

    def test_heute_button_displayed_on_future_week(self):
        """Calendar shows a 'Heute' button when not on current week."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk, "week": "3"})
        assert "Heute" in resp.content.decode()

    def test_heute_button_hidden_on_current_week(self):
        """'Heute' button not shown when already on week 0."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk, "week": "0"})
        content = resp.content.decode()
        # On week 0, the Heute button should not be present in the HTMX nav
        assert 'week=0"' not in content or "Heute" not in content.split("week=0")[0]

    def test_next_button_disabled_at_week_52(self):
        """Next week button is disabled at the maximum week offset."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk, "week": "52"}, HTTP_HX_REQUEST="true")
        content = resp.content.decode()
        # Next button should be a disabled span like the prev button at week 0
        assert "Nächste</span>" in content or 'text-slate-300">Nächste' in content

    def test_week_state_preserved_in_htmx_response(self):
        """HTMX week navigation response includes OOB swap for week input."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(
            url,
            {"apartment": apt.pk, "week": "3"},
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        assert 'id="week-input"' in content
        assert "hx-swap-oob" in content
        assert 'value="3"' in content

    def test_full_page_renders_single_week_input(self):
        """Initial full page load does not duplicate the week state input."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        content = resp.content.decode()
        assert content.count('id="week-input"') == 1
        assert "hx-swap-oob" not in content

    def test_week_navigation_pushes_browser_url(self):
        """Week navigation updates the browser URL as well as the calendar partial."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        content = resp.content.decode()
        assert 'hx-push-url="true"' in content
        assert 'hx-disinherit="hx-include"' in content

    def test_booked_slot_shows_apartment_name(self):
        """Owner's booked slot displays the apartment name."""
        owner, sub, apt, client, url = self._setup()
        target_date = _future_date(days_ahead=5)
        InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot=Inspection.TimeSlot.MORNING,
            status=Inspection.Status.SCHEDULED,
        )
        # Navigate to the week containing the booking
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        week_offset = (target_date - start_of_week).days // 7
        resp = client.get(url, {"apartment": apt.pk, "week": str(week_offset)})
        content = resp.content.decode()
        # Apartment name should appear (truncated)
        assert "Teststraße" in content
        assert "bg-amber-50" in content

    def test_other_owner_booked_slot_shows_taken(self):
        """Slot booked by another owner shows as taken without apartment details."""
        owner, sub, apt, client, url = self._setup()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner, address="Andere Gasse 5, 1020 Wien")
        target_date = _future_date(days_ahead=5)
        InspectionFactory(
            apartment=other_apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            time_slot=Inspection.TimeSlot.MORNING,
            status=Inspection.Status.SCHEDULED,
        )
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        week_offset = (target_date - start_of_week).days // 7
        resp = client.get(url, {"apartment": apt.pk, "week": str(week_offset)})
        assert "Andere Gasse" not in resp.content.decode()

    def test_booked_by_me_slot_has_distinct_style(self):
        """Slots booked by the current owner have amber/accent styling."""
        owner, sub, apt, client, url = self._setup()
        target_date = _future_date(days_ahead=5)
        InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            time_slot=Inspection.TimeSlot.MORNING,
            status=Inspection.Status.SCHEDULED,
        )
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        week_offset = (target_date - start_of_week).days // 7
        resp = client.get(url, {"apartment": apt.pk, "week": str(week_offset)})
        assert "bg-amber-50" in resp.content.decode()

    def test_slot_has_aria_label(self):
        """Slots include aria-label with context."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        assert "aria-label=" in resp.content.decode()

    def test_booking_success_triggers_calendar_refresh(self):
        """Successful booking response includes HX-Trigger header."""
        owner, sub, apt, client, url = self._setup()
        target_date = _future_date(days_ahead=5)
        resp = client.post(
            reverse("dashboard:book_slot"),
            {"apartment": apt.pk, "date": target_date.isoformat(), "slot": "morning"},
        )
        assert resp.headers.get("HX-Trigger") == "calendarChanged"

    def test_cancel_success_triggers_calendar_refresh(self):
        """Successful cancellation response includes HX-Trigger header."""
        owner, sub, apt, client, url = self._setup()
        target_date = _future_date(days_ahead=5)
        inspection = InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            time_slot=Inspection.TimeSlot.MORNING,
            status=Inspection.Status.SCHEDULED,
        )
        resp = client.post(reverse("dashboard:cancel_booking", args=[inspection.pk]))
        assert resp.headers.get("HX-Trigger") == "calendarChanged"

    def test_cancellation_policy_visible(self):
        """Cancellation policy text is visible on the calendar page."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        assert "24 Stunden" in resp.content.decode()

    def test_calendar_page_has_mobile_and_desktop_layout(self):
        """Calendar page renders with both mobile and desktop layouts."""
        owner, sub, apt, client, url = self._setup()
        resp = client.get(url, {"apartment": apt.pk})
        content = resp.content.decode()
        assert "md:hidden" in content
        assert "md:grid" in content


@pytest.mark.django_db
class TestCancellationConfirmView:
    """Test the two-step cancellation confirmation flow."""

    def _create_inspection(self, owner, days_ahead=5):
        apt = ApartmentFactory(owner=owner)
        target_date = _future_date(days_ahead=days_ahead)
        return InspectionFactory(
            apartment=apt,
            scheduled_at=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ
            ),
            scheduled_end=datetime.datetime(
                target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ
            ),
            status=Inspection.Status.SCHEDULED,
            time_slot=Inspection.TimeSlot.MORNING,
        )

    def test_confirm_view_shows_timely_cancellation_info(self):
        """Confirmation partial shows 'free cancellation' for >24h bookings."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner, days_ahead=5)
        client = Client()
        client.force_login(owner)

        resp = client.get(reverse("dashboard:confirm_cancellation", args=[inspection.pk]))
        assert resp.status_code == 200
        assert "Kostenlose Stornierung" in resp.content.decode()

    def test_confirm_view_shows_late_cancellation_warning(self):
        """Confirmation partial warns about quota charge for <24h bookings."""
        from unittest.mock import patch

        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner, days_ahead=1)

        fake_now = inspection.scheduled_at - datetime.timedelta(hours=12)
        client = Client()
        client.force_login(owner)

        with patch("apps.dashboard.views.timezone.now", return_value=fake_now):
            resp = client.get(reverse("dashboard:confirm_cancellation", args=[inspection.pk]))
        assert resp.status_code == 200
        assert "Kontingent wird belastet" in resp.content.decode()

    def test_confirm_view_requires_owner(self):
        """Other users cannot see cancellation confirmation."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)

        other_owner = OwnerFactory()
        SubscriptionFactory(owner=other_owner)
        ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(other_owner)

        resp = client.get(reverse("dashboard:confirm_cancellation", args=[inspection.pk]))
        assert resp.status_code == 404

    def test_confirm_view_requires_login(self):
        """Unauthenticated users redirected to login."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner)
        client = Client()
        resp = client.get(reverse("dashboard:confirm_cancellation", args=[inspection.pk]))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_confirm_view_shows_apartment_and_date(self):
        """Confirmation shows apartment address and date/time."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner)
        inspection = self._create_inspection(owner, days_ahead=5)
        client = Client()
        client.force_login(owner)

        resp = client.get(reverse("dashboard:confirm_cancellation", args=[inspection.pk]))
        content = resp.content.decode()
        assert inspection.apartment.address in content
        assert "08:00" in content
