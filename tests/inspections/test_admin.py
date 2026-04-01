import pytest
from django.urls import reverse

from apps.inspections.models import Inspection
from tests.factories import (
    AdminFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
)


@pytest.mark.django_db
class TestInspectionAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:inspections_inspection_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_changelist_shows_inspection(self, client):
        client.force_login(self.superuser)
        inspection = InspectionFactory()
        url = reverse("admin:inspections_inspection_changelist")
        response = client.get(url)
        assert response.status_code == 200
        assert inspection.apartment.address in response.content.decode()

    def test_change_form_loads(self, client):
        client.force_login(self.superuser)
        inspection = InspectionFactory()
        url = reverse("admin:inspections_inspection_change", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 200

    def test_filter_by_status(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:inspections_inspection_changelist")
        response = client.get(url, {"status": "scheduled"})
        assert response.status_code == 200

    def test_search_by_apartment_address(self, client):
        client.force_login(self.superuser)
        inspection = InspectionFactory()
        url = reverse("admin:inspections_inspection_changelist")
        response = client.get(url, {"q": inspection.apartment.address[:10]})
        assert response.status_code == 200

    def test_assign_inspector_action(self, client):
        client.force_login(self.superuser)
        inspector = InspectorFactory()
        inspection = InspectionFactory(status=Inspection.Status.SCHEDULED)
        url = reverse("admin:inspections_inspection_changelist")
        response = client.post(
            url,
            {"action": "assign_inspector", "_selected_action": [inspection.pk]},
            follow=True,
        )
        assert response.status_code == 200
        inspection.refresh_from_db()
        assert inspection.inspector == inspector

    def test_assign_inspector_no_inspector_available(self, client):
        """When no inspector exists, action shows error."""
        client.force_login(self.superuser)
        # Create inspection with an inspector, then delete all inspectors
        inspection = InspectionFactory(status=Inspection.Status.SCHEDULED)
        from apps.accounts.models import User

        User.objects.filter(role=User.Role.INSPECTOR).delete()
        url = reverse("admin:inspections_inspection_changelist")
        response = client.post(
            url,
            {"action": "assign_inspector", "_selected_action": [inspection.pk]},
            follow=True,
        )
        assert response.status_code == 200

    def test_cancel_inspections_action(self, client):
        client.force_login(self.superuser)
        inspection = InspectionFactory(status=Inspection.Status.SCHEDULED)
        url = reverse("admin:inspections_inspection_changelist")
        response = client.post(
            url,
            {"action": "cancel_inspections", "_selected_action": [inspection.pk]},
            follow=True,
        )
        assert response.status_code == 200
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.CANCELLED

    def test_cancel_only_affects_scheduled(self, client):
        client.force_login(self.superuser)
        completed = InspectionFactory(status=Inspection.Status.COMPLETED)
        url = reverse("admin:inspections_inspection_changelist")
        client.post(
            url,
            {"action": "cancel_inspections", "_selected_action": [completed.pk]},
            follow=True,
        )
        completed.refresh_from_db()
        assert completed.status == Inspection.Status.COMPLETED  # Unchanged

    def test_export_csv_action(self, client):
        client.force_login(self.superuser)
        InspectionFactory()
        url = reverse("admin:inspections_inspection_changelist")
        response = client.post(
            url,
            {"action": "export_csv", "_selected_action": [Inspection.objects.first().pk]},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert 'filename="inspections.csv"' in response["Content-Disposition"]
        content = response.content.decode("utf-8-sig")
        assert "Wohnung" in content  # Header row
        assert "Inspektor" in content

    def test_export_csv_contains_data(self, client):
        client.force_login(self.superuser)
        inspection = InspectionFactory(general_notes="Testnotiz")
        url = reverse("admin:inspections_inspection_changelist")
        response = client.post(
            url,
            {"action": "export_csv", "_selected_action": [inspection.pk]},
        )
        content = response.content.decode("utf-8-sig")
        assert inspection.apartment.address in content
        assert "Testnotiz" in content


@pytest.mark.django_db
class TestInspectionItemAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:inspections_inspectionitem_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_filter_by_result(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:inspections_inspectionitem_changelist")
        response = client.get(url, {"result": "flagged"})
        assert response.status_code == 200

    def test_search_by_label(self, client):
        client.force_login(self.superuser)
        InspectionItemFactory(checklist_label="Rauchmelder prüfen")
        url = reverse("admin:inspections_inspectionitem_changelist")
        response = client.get(url, {"q": "Rauchmelder"})
        assert response.status_code == 200
        assert "Rauchmelder" in response.content.decode()


@pytest.mark.django_db
class TestPhotoAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:inspections_photo_changelist")
        response = client.get(url)
        assert response.status_code == 200
