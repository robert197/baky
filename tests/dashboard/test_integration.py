import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    OwnerFactory,
    PhotoFactory,
    ReportFactory,
)


@pytest.mark.django_db
class TestDashboardIntegration:
    def test_owner_full_flow(self):
        """Owner: login -> dashboard -> see apartments -> edit -> save -> back to dashboard."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)

        # See dashboard
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

        # Navigate to detail
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

        # Navigate to edit
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        assert response.status_code == 200

        # Save changes
        response = client.post(
            reverse("dashboard:apartment_edit", args=[apt.pk]),
            {
                "address": "Geaenderte Adresse 1, 1010 Wien",
                "access_method": "smart_lock",
                "access_code": "app-code-123",
                "access_notes": "App oeffnen",
                "special_instructions": "",
                "status": "active",
            },
            follow=True,
        )
        assert response.status_code == 200
        assert "Geaenderte Adresse" in response.content.decode()

    def test_owner_with_inspections_sees_data(self):
        """Dashboard cards show inspection info."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="completed",
            overall_rating="attention",
            completed_at=timezone.now() - datetime.timedelta(days=2),
        )
        InspectionFactory(
            apartment=apt,
            status="scheduled",
            scheduled_at=timezone.now() + datetime.timedelta(days=3),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_multi_apartment_owner(self):
        """Owner with multiple apartments sees all of them."""
        owner = OwnerFactory()
        apt1 = ApartmentFactory(owner=owner, address="Wohnung Eins")
        apt2 = ApartmentFactory(owner=owner, address="Wohnung Zwei")
        apt3 = ApartmentFactory(owner=owner, address="Wohnung Drei")
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        content = response.content.decode()
        assert apt1.address in content
        assert apt2.address in content
        assert apt3.address in content

    def test_security_cross_owner_access(self):
        """Owner A cannot access Owner B's apartments through any view."""
        owner_a = OwnerFactory()
        owner_b = OwnerFactory()
        apt_b = ApartmentFactory(owner=owner_b)
        client = Client()
        client.force_login(owner_a)

        assert client.get(reverse("dashboard:apartment_detail", args=[apt_b.pk])).status_code == 404
        assert client.get(reverse("dashboard:apartment_edit", args=[apt_b.pk])).status_code == 404
        assert (
            client.post(
                reverse("dashboard:apartment_edit", args=[apt_b.pk]),
                {
                    "address": "Hacked",
                    "access_method": "lockbox",
                    "access_code": "",
                    "access_notes": "",
                    "special_instructions": "",
                    "status": "active",
                },
            ).status_code
            == 404
        )

    def test_apartment_to_timeline_to_report(self):
        """Full flow: apartment detail -> timeline -> summary -> report detail."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(first_name="Anna", last_name="Schmidt")
        insp = InspectionFactory(
            apartment=apt,
            inspector=inspector,
            status="completed",
            overall_rating="attention",
            completed_at=timezone.now(),
        )
        InspectionItemFactory(inspection=insp, category="Küche", result="ok")
        InspectionItemFactory(inspection=insp, category="Küche", result="flagged", severity="medium")
        PhotoFactory(inspection=insp, caption="Küchenregal")
        ReportFactory(inspection=insp)

        client = Client()
        client.force_login(owner)

        # Step 1: Apartment detail shows timeline link
        resp = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert resp.status_code == 200
        assert reverse("dashboard:inspection_timeline", args=[apt.pk]) in resp.content.decode()

        # Step 2: Timeline shows the inspection
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert "Anna Schmidt" in resp.content.decode()

        # Step 3: Summary expansion
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200

        # Step 4: Report detail shows items, photos, inspector
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Küche" in content
        assert "Küchenregal" in content
        assert "Anna Schmidt" in content

    def test_cross_owner_inspection_access_blocked(self):
        """Owner A cannot view Owner B's inspection timeline or report."""
        owner_a = OwnerFactory()
        owner_b = OwnerFactory()
        apt_b = ApartmentFactory(owner=owner_b)
        insp = InspectionFactory(apartment=apt_b, status="completed", completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner_a)

        assert client.get(reverse("dashboard:inspection_timeline", args=[apt_b.pk])).status_code == 404
        assert client.get(reverse("dashboard:inspection_summary", args=[apt_b.pk, insp.pk])).status_code == 404
        assert client.get(reverse("dashboard:inspection_report_detail", args=[apt_b.pk, insp.pk])).status_code == 404

    def test_pause_apartment_via_edit(self):
        """Owner can pause their apartment via the edit form."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner, status="active")
        client = Client()
        client.force_login(owner)
        response = client.post(
            reverse("dashboard:apartment_edit", args=[apt.pk]),
            {
                "address": apt.address,
                "access_method": apt.access_method,
                "access_code": "",
                "access_notes": "",
                "special_instructions": "",
                "status": "paused",
            },
        )
        assert response.status_code == 302
        apt.refresh_from_db()
        assert apt.status == "paused"
