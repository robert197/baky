import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import DataExportRequest
from apps.inspections.models import Inspection
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
)


@pytest.mark.django_db
class TestAccountDeletion:
    def test_delete_request_requires_login(self):
        client = Client()
        response = client.get(reverse("dashboard:account_delete"))
        assert response.status_code == 302

    def test_delete_request_requires_owner_role(self):
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("dashboard:account_delete"))
        assert response.status_code == 404

    def test_delete_request_page_renders(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:account_delete"))
        assert response.status_code == 200
        assert "Konto" in response.content.decode()

    def test_delete_request_requires_password(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:account_delete"), {"password": "wrong"})
        assert response.status_code == 200
        owner.refresh_from_db()
        assert owner.deleted_at is None

    def test_delete_request_success(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:account_delete"), {"password": "testpass123"})
        assert response.status_code == 302
        owner.refresh_from_db()
        assert owner.deleted_at is not None
        assert owner.is_active is False

    def test_delete_blocks_if_inspection_in_progress(self):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        InspectionFactory(apartment=apartment, status="in_progress")
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:account_delete"), {"password": "testpass123"})
        assert response.status_code == 200
        owner.refresh_from_db()
        assert owner.deleted_at is None

    def test_delete_cancels_scheduled_inspections(self):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status="scheduled")
        client = Client()
        client.force_login(owner)
        client.post(reverse("dashboard:account_delete"), {"password": "testpass123"})
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.CANCELLED


@pytest.mark.django_db
class TestAccountDeleteCancel:
    def test_cancel_page_renders(self):
        client = Client()
        response = client.get(reverse("accounts:account-delete-cancel"))
        assert response.status_code == 200

    def test_cancel_with_valid_credentials(self):
        owner = OwnerFactory(deleted_at=timezone.now(), is_active=False)
        client = Client()
        response = client.post(
            reverse("accounts:account-delete-cancel"),
            {"email": owner.email, "password": "testpass123"},
        )
        assert response.status_code == 302
        owner.refresh_from_db()
        assert owner.deleted_at is None
        assert owner.is_active is True

    def test_cancel_with_wrong_password(self):
        owner = OwnerFactory(deleted_at=timezone.now(), is_active=False)
        client = Client()
        response = client.post(
            reverse("accounts:account-delete-cancel"),
            {"email": owner.email, "password": "wrongpassword"},
        )
        assert response.status_code == 200
        owner.refresh_from_db()
        assert owner.deleted_at is not None

    def test_cancel_with_nonexistent_email(self):
        client = Client()
        response = client.post(
            reverse("accounts:account-delete-cancel"),
            {"email": "nobody@example.com", "password": "testpass123"},
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestDataExportView:
    def test_export_request_requires_login(self):
        client = Client()
        response = client.get(reverse("dashboard:data_export"))
        assert response.status_code == 302

    def test_export_request_page_renders(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:data_export"))
        assert response.status_code == 200
        assert "Datenexport" in response.content.decode()

    def test_export_request_creates_record(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:data_export"))
        assert response.status_code == 302
        assert DataExportRequest.objects.filter(user=owner).exists()

    def test_export_request_prevents_duplicate_pending(self):
        owner = OwnerFactory()
        DataExportRequest.objects.create(user=owner, status="PENDING")
        client = Client()
        client.force_login(owner)
        client.post(reverse("dashboard:data_export"))
        # Should still redirect, but not create a second request
        assert DataExportRequest.objects.filter(user=owner).count() == 1

    def test_export_shows_pending_status(self):
        owner = OwnerFactory()
        DataExportRequest.objects.create(user=owner, status="PENDING")
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:data_export"))
        content = response.content.decode()
        assert "wird erstellt" in content
