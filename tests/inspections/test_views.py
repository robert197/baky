"""Tests for inspector schedule views."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inspections.models import Inspection, InspectionItem
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    OwnerFactory,
)


def _tomorrow_at(hour: int = 10) -> datetime.datetime:
    """Return tomorrow at the given hour in the current timezone."""
    return timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)


def _yesterday_at(hour: int = 10) -> datetime.datetime:
    """Return yesterday at the given hour."""
    return timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1)


@pytest.mark.django_db
class TestScheduleView:
    def test_requires_authentication(self):
        client = Client()
        url = reverse("inspections:schedule")
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_owner_gets_404(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:schedule")
        response = client.get(url)
        assert response.status_code == 404

    def test_inspector_sees_schedule(self):
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:schedule")
        response = client.get(url)
        assert response.status_code == 200
        assert "Meine Termine" in response.content.decode()

    def test_shows_upcoming_inspections(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:schedule")
        response = client.get(url)
        content = response.content.decode()
        assert apt.street in content

    def test_does_not_show_other_inspectors_inspections(self):
        inspector1 = InspectorFactory()
        inspector2 = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector2,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector1)
        url = reverse("inspections:schedule")
        response = client.get(url)
        content = response.content.decode()
        assert apt.street not in content

    def test_does_not_show_past_inspections(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        yesterday = _yesterday_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=yesterday,
            scheduled_end=yesterday + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:schedule")
        response = client.get(url)
        content = response.content.decode()
        assert apt.street not in content

    def test_does_not_show_cancelled_inspections(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.CANCELLED,
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:schedule")
        response = client.get(url)
        content = response.content.decode()
        assert apt.street not in content

    def test_empty_state_shown(self):
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:schedule")
        response = client.get(url)
        content = response.content.decode()
        assert "Keine anstehenden Termine" in content

    def test_inspections_ordered_by_scheduled_at(self):
        inspector = InspectorFactory()
        apt1 = ApartmentFactory(street="Zweite Straße")
        apt2 = ApartmentFactory(street="Erste Straße")
        tomorrow_early = _tomorrow_at(10)
        tomorrow_late = _tomorrow_at(14)
        InspectionFactory(
            inspector=inspector,
            apartment=apt1,
            scheduled_at=tomorrow_late,
            scheduled_end=tomorrow_late + datetime.timedelta(hours=2),
        )
        InspectionFactory(
            inspector=inspector,
            apartment=apt2,
            scheduled_at=tomorrow_early,
            scheduled_end=tomorrow_early + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:schedule")
        response = client.get(url)
        content = response.content.decode()
        erste_pos = content.index("Erste Straße")
        zweite_pos = content.index("Zweite Straße")
        assert erste_pos < zweite_pos

    # --- Owner name display ---

    def test_shows_owner_name(self):
        """Owner's full name (or username) should appear on each inspection card."""
        inspector = InspectorFactory()
        owner = OwnerFactory(first_name="Maria", last_name="Huber")
        apt = ApartmentFactory(owner=owner)
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "Maria Huber" in content

    def test_shows_owner_username_when_no_full_name(self):
        """Falls back to username when first/last name not set."""
        inspector = InspectorFactory()
        owner = OwnerFactory(username="mhuber", first_name="", last_name="")
        apt = ApartmentFactory(owner=owner)
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "mhuber" in content

    # --- Navigation link ---

    def test_shows_navigation_link(self):
        """Each inspection card should have a maps navigation link."""
        inspector = InspectorFactory()
        apt = ApartmentFactory(address="Stephansplatz 1, 1010 Wien")
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "maps" in content.lower()
        assert apt.maps_url in content or "google.com/maps" in content

    # --- Access details hidden by default ---

    def test_access_details_not_in_initial_payload(self):
        """Access code/notes should NOT be in the initial HTML — loaded via HTMX on tap."""
        inspector = InspectorFactory()
        apt = ApartmentFactory(access_code="1234", access_notes="Schlüssel unter der Matte")
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        # Access method label is present
        assert apt.get_access_method_display() in content
        # But the sensitive access code is NOT in the initial payload
        assert "1234" not in content
        assert "Schlüssel unter der Matte" not in content
        # HTMX attributes are present for lazy-loading
        assert "hx-get" in content
        assert "hx-trigger" in content

    # --- Previous inspection context ---

    def test_shows_previous_inspection_rating(self):
        """Previous completed inspection's overall rating should appear."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        # Create a past completed inspection
        past = _yesterday_at()
        past_inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=past,
            scheduled_end=past + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=past + datetime.timedelta(hours=2),
            overall_rating=Inspection.OverallRating.ATTENTION,
        )
        InspectionItemFactory(
            inspection=past_inspection,
            result=InspectionItem.Result.FLAGGED,
            checklist_label="Fenster beschädigt",
        )
        # Create upcoming inspection for same apartment
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "Achtung" in content  # OverallRating.ATTENTION display value
        assert "Fenster beschädigt" in content

    def test_no_previous_inspection_shows_first_visit(self):
        """When no previous inspection exists, show a 'first visit' indicator."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "Erstbesuch" in content

    # --- Start inspection button ---

    def test_shows_start_inspection_button(self):
        """Each scheduled inspection should have a start button."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "Inspektion starten" in content

    # --- Date grouping ---

    def test_today_label_shown_for_todays_inspections(self):
        """Inspections for today should be labeled 'Heute'."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        now = timezone.now()
        # Schedule for today within business hours
        today_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if today_10am < now:
            today_10am = now.replace(hour=14, minute=0, second=0, microsecond=0)
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=today_10am,
            scheduled_end=today_10am + datetime.timedelta(hours=2),
            status=Inspection.Status.IN_PROGRESS,
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "Heute" in content

    # --- German umlauts ---

    def test_handles_german_characters(self):
        """Addresses with German umlauts should display correctly."""
        inspector = InspectorFactory()
        apt = ApartmentFactory(street="Währinger Straße", city="Wien")
        tomorrow = _tomorrow_at()
        InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("inspections:schedule"))
        content = response.content.decode()
        assert "Währinger Straße" in content


@pytest.mark.django_db
class TestScheduleAccessDetailsView:
    """Tests for the HTMX endpoint that returns access details."""

    def test_returns_access_details_for_valid_inspection(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory(
            access_method="lockbox",
            access_code="4321",
            access_notes="Schlüsselbox neben der Tür",
        )
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:access_details", args=[inspection.pk])
        response = client.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        content = response.content.decode()
        assert "4321" in content
        assert "Schlüsselbox neben der Tür" in content

    def test_requires_authentication(self):
        client = Client()
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        url = reverse("inspections:access_details", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 302

    def test_other_inspector_gets_404(self):
        inspector1 = InspectorFactory()
        inspector2 = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector1,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(inspector2)
        url = reverse("inspections:access_details", args=[inspection.pk])
        response = client.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_owner_gets_404(self):
        owner = OwnerFactory()
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
        )
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:access_details", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestIndexView:
    def test_index_redirects_to_schedule(self):
        """Index view should show the schedule."""
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:index")
        response = client.get(url)
        assert response.status_code == 200
        assert "Meine Termine" in response.content.decode()
