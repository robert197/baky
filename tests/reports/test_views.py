"""Tests for report views."""

import pytest

from apps.inspections.models import Inspection
from apps.reports.models import Report
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
    PhotoFactory,
    ReportFactory,
)


@pytest.mark.django_db
class TestReportDetailView:
    def test_owner_can_view_own_report(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection)
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert report.html_content in content

    def test_requires_owner_role(self, client):
        inspector = InspectorFactory()
        report = ReportFactory()
        client.force_login(inspector)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 404

    def test_returns_404_for_other_owners_report(self, client):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        apartment = ApartmentFactory(owner=other_owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection)
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 404

    def test_unauthenticated_redirects_to_login(self, client):
        report = ReportFactory()
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_pending_report_shows_status_message(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection, status=Report.Status.PENDING, html_content="")
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "wird erstellt" in content.lower() or "erstellt" in content.lower()

    def test_failed_report_shows_error_state(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(
            inspection=inspection, status=Report.Status.FAILED, html_content="", error_message="Template error"
        )
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 200

    def test_returns_404_for_nonexistent_report(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get("/dashboard/reports/999999/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestReportPhotoView:
    def test_redirects_to_signed_url(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        ReportFactory(inspection=inspection)
        photo = PhotoFactory(inspection=inspection)
        client.force_login(owner)
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 302

    def test_requires_authentication(self, client):
        photo = PhotoFactory()
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_returns_404_for_wrong_owner(self, client):
        other_owner = OwnerFactory()
        apartment = ApartmentFactory(owner=OwnerFactory())
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        photo = PhotoFactory(inspection=inspection)
        client.force_login(other_owner)
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 404

    def test_returns_404_for_nonexistent_photo(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get("/reports/photos/999999/")
        assert response.status_code == 404

    def test_inspector_cannot_access(self, client):
        inspector = InspectorFactory()
        photo = PhotoFactory()
        client.force_login(inspector)
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 404
