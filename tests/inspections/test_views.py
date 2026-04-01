"""Tests for inspector schedule views."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inspections.models import Inspection
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
)


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
        tomorrow = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
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
        tomorrow = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
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
        yesterday = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1)
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
        tomorrow = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
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
        tomorrow_early = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        tomorrow_late = timezone.now().replace(hour=14, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
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
