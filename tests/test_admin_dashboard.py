import datetime

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from baky.admin_dashboard import dashboard_callback
from tests.factories import AdminFactory, ApartmentFactory, InspectionFactory, InspectionItemFactory


@pytest.mark.django_db
class TestDashboardCallback:
    def test_returns_context_with_metrics(self):
        request = RequestFactory().get("/admin/")
        context = {}
        result = dashboard_callback(request, context)

        assert "active_apartments" in result
        assert "inspections_this_week" in result
        assert "pending_inspections" in result
        assert "urgent_findings" in result

    def test_active_apartments_count(self):
        ApartmentFactory(status="active")
        ApartmentFactory(status="active")
        ApartmentFactory(status="paused")

        request = RequestFactory().get("/admin/")
        result = dashboard_callback(request, {})
        assert result["active_apartments"] == 2

    def test_pending_inspections_count(self):
        InspectionFactory(status="scheduled")
        InspectionFactory(status="scheduled")
        InspectionFactory(status="completed")

        request = RequestFactory().get("/admin/")
        result = dashboard_callback(request, {})
        assert result["pending_inspections"] == 2

    def test_urgent_findings_in_last_week(self):
        recent_inspection = InspectionFactory(
            status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=2),
        )
        InspectionItemFactory(
            inspection=recent_inspection,
            severity="urgent",
        )
        # Old urgent finding — should not count
        old_inspection = InspectionFactory(
            status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=10),
        )
        InspectionItemFactory(
            inspection=old_inspection,
            severity="urgent",
        )

        request = RequestFactory().get("/admin/")
        result = dashboard_callback(request, {})
        assert result["urgent_findings"] == 1

    def test_zero_counts_when_empty(self):
        request = RequestFactory().get("/admin/")
        result = dashboard_callback(request, {})
        assert result["active_apartments"] == 0
        assert result["inspections_this_week"] == 0
        assert result["pending_inspections"] == 0
        assert result["urgent_findings"] == 0

    def test_preserves_existing_context(self):
        request = RequestFactory().get("/admin/")
        context = {"existing_key": "existing_value"}
        result = dashboard_callback(request, context)
        assert result["existing_key"] == "existing_value"


@pytest.mark.django_db
class TestAdminDashboardView:
    def test_dashboard_loads_for_superuser(self, client):
        superuser = AdminFactory(is_staff=True, is_superuser=True)
        client.force_login(superuser)
        url = reverse("admin:index")
        response = client.get(url)
        assert response.status_code == 200

    def test_dashboard_shows_metric_labels(self, client):
        superuser = AdminFactory(is_staff=True, is_superuser=True)
        client.force_login(superuser)
        ApartmentFactory(status="active")
        url = reverse("admin:index")
        response = client.get(url)
        content = response.content.decode()
        assert "Aktive Wohnungen" in content
        assert "Inspektionen diese Woche" in content
        assert "Offene Inspektionen" in content

    def test_dashboard_redirects_non_staff(self, client):
        from tests.factories import UserFactory

        user = UserFactory()
        client.force_login(user)
        url = reverse("admin:index")
        response = client.get(url)
        assert response.status_code == 302
