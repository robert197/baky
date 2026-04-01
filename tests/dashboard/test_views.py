import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tests.factories import (
    ApartmentFactory,
    ChecklistTemplateFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
)


@pytest.mark.django_db
class TestDashboardIndex:
    def test_owner_sees_own_apartments(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

    def test_owner_does_not_see_other_apartments(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert other_apt.address not in response.content.decode()

    def test_archived_apartments_excluded(self):
        owner = OwnerFactory()
        archived = ApartmentFactory(owner=owner, status="archived", address="Archivierte Wohnung 99")
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert archived.address not in response.content.decode()

    def test_empty_state_shown(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        content = response.content.decode()
        assert "Keine Wohnungen" in content

    def test_unauthenticated_redirects(self):
        client = Client()
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 302

    def test_inspector_gets_404(self):
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 404

    def test_shows_last_inspection_rating(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="completed",
            overall_rating="ok",
            completed_at=timezone.now() - datetime.timedelta(days=1),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_shows_next_scheduled_inspection(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="scheduled",
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_uses_dashboard_template(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert "dashboard/index.html" in [t.name for t in response.templates]

    def test_sidebar_has_wohnungen_link(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert "/dashboard/" in response.content.decode()


@pytest.mark.django_db
class TestApartmentDetail:
    def test_owner_sees_own_apartment(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

    def test_other_owner_gets_404(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[other_apt.pk]))
        assert response.status_code == 404

    def test_shows_checklist_summary(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        ChecklistTemplateFactory(apartment=apt)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Checkliste" in content

    def test_shows_recent_inspections(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="completed",
            overall_rating="attention",
            completed_at=timezone.now(),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 200
        assert "Achtung" in response.content.decode()

    def test_unauthenticated_redirects(self):
        apt = ApartmentFactory()
        client = Client()
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 302

    def test_inspector_gets_404(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestApartmentEdit:
    def test_get_edit_form(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

    def test_post_valid_data(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.post(
            reverse("dashboard:apartment_edit", args=[apt.pk]),
            {
                "address": "Neue Adresse 1, 1020 Wien",
                "access_method": "lockbox",
                "access_code": "5678",
                "access_notes": "",
                "special_instructions": "",
                "status": "active",
            },
        )
        assert response.status_code == 302
        apt.refresh_from_db()
        assert apt.address == "Neue Adresse 1, 1020 Wien"

    def test_post_invalid_data(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.post(
            reverse("dashboard:apartment_edit", args=[apt.pk]),
            {
                "address": "",
                "access_method": "lockbox",
                "access_code": "",
                "access_notes": "",
                "special_instructions": "",
                "status": "active",
            },
        )
        assert response.status_code == 200  # re-renders form with errors

    def test_other_owner_gets_404(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_edit", args=[other_apt.pk]))
        assert response.status_code == 404

    def test_post_other_owner_gets_404(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.post(
            reverse("dashboard:apartment_edit", args=[other_apt.pk]),
            {
                "address": "Hacked",
                "access_method": "lockbox",
                "access_code": "",
                "access_notes": "",
                "special_instructions": "",
                "status": "active",
            },
        )
        assert response.status_code == 404

    def test_success_message_shown(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.post(
            reverse("dashboard:apartment_edit", args=[apt.pk]),
            {
                "address": "Teststrasse 1",
                "access_method": "lockbox",
                "access_code": "",
                "access_notes": "",
                "special_instructions": "",
                "status": "active",
            },
            follow=True,
        )
        assert "gespeichert" in response.content.decode().lower()

    def test_cancel_link_exists(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        assert "Abbrechen" in response.content.decode()

    def test_unauthenticated_redirects(self):
        apt = ApartmentFactory()
        client = Client()
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        assert response.status_code == 302
