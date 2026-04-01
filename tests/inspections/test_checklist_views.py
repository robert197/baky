"""Tests for checklist execution views."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inspections.models import Inspection, InspectionItem
from tests.factories import (
    ApartmentFactory,
    ChecklistTemplateFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    OwnerFactory,
    SubscriptionFactory,
)


def _tomorrow_at(hour: int = 10) -> datetime.datetime:
    """Return tomorrow at the given hour in the current timezone."""
    return timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)


def _create_inspection_with_template(inspector, **kwargs):
    """Create an inspection with a checklist template on the apartment.

    Note: ApartmentFactory triggers a post_save signal that auto-creates a 22-item
    default ChecklistTemplate. We use that directly.
    """
    apt = kwargs.pop("apartment", None) or ApartmentFactory()
    SubscriptionFactory(owner=apt.owner)
    # Apartment already has a checklist_template from the post_save signal
    tomorrow = _tomorrow_at()
    return InspectionFactory(
        inspector=inspector,
        apartment=apt,
        scheduled_at=kwargs.pop("scheduled_at", tomorrow),
        scheduled_end=kwargs.pop("scheduled_end", tomorrow + datetime.timedelta(hours=2)),
        **kwargs,
    )


# --- Start Inspection ---


@pytest.mark.django_db
class TestStartInspectionView:
    def test_start_creates_items_from_template(self):
        """Starting an inspection creates InspectionItems from the apartment's checklist template."""
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        response = client.post(url)
        # Should redirect to the execute page
        assert response.status_code == 302
        assert str(inspection.pk) in response.url
        # Items created from the 22-item default checklist template (auto-created by signal)
        assert inspection.items.count() == 22
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.IN_PROGRESS
        assert inspection.started_at is not None

    def test_start_sets_correct_item_fields(self):
        """InspectionItems should have category, label, and order from the template."""
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        client.post(url)
        items = list(inspection.items.order_by("order"))
        # First item from the 22-item default checklist
        assert items[0].checklist_label == "Wohnung wirkt sauber und ordentlich"
        assert items[0].category == "Allgemeiner Eindruck"
        assert items[0].order == 1
        assert items[1].checklist_label == "Keine ungewöhnlichen Gerüche festgestellt"
        assert items[1].category == "Allgemeiner Eindruck"

    def test_start_requires_authentication(self):
        client = Client()
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        response = client.post(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_start_requires_inspector_role(self):
        owner = OwnerFactory()
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector)
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        response = client.post(url)
        assert response.status_code == 404

    def test_start_only_assigned_inspector(self):
        """Another inspector cannot start someone else's inspection."""
        inspector1 = InspectorFactory()
        inspector2 = InspectorFactory()
        inspection = _create_inspection_with_template(inspector1)
        client = Client()
        client.force_login(inspector2)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        response = client.post(url)
        assert response.status_code == 404

    def test_start_already_in_progress_redirects(self):
        """Starting an already in-progress inspection just redirects to execute."""
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector, status=Inspection.Status.IN_PROGRESS)
        # Pre-create items (simulating already started)
        InspectionItemFactory(inspection=inspection, order=1)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        response = client.post(url)
        assert response.status_code == 302
        # Should not create duplicate items
        assert inspection.items.count() == 1

    def test_start_requires_post(self):
        """GET should not be allowed for starting an inspection."""
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:start_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 405


# --- Execute Inspection (Checklist Page) ---


@pytest.mark.django_db
class TestExecuteInspectionView:
    def _setup_in_progress(self, inspector=None):
        """Create an in-progress inspection with items from the default checklist."""
        inspector = inspector or InspectorFactory()
        inspection = _create_inspection_with_template(
            inspector,
            status=Inspection.Status.IN_PROGRESS,
        )
        # Create items from the apartment's checklist template (22-item default)
        template = inspection.apartment.checklist_template
        for item_data in template.items:
            InspectionItemFactory(
                inspection=inspection,
                checklist_label=item_data["label"],
                category=item_data["category"],
                order=item_data["order"],
                result=InspectionItem.Result.OK,
            )
        return inspector, inspection

    def test_displays_checklist_items(self):
        inspector, inspection = self._setup_in_progress()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Items from the 22-item default checklist
        assert "Wohnung wirkt sauber und ordentlich" in content
        assert "Herd/Ofen sauber" in content
        assert "Keine Wasserschäden" not in content  # This label is from the factory, not default
        assert "Kein Schimmel oder Feuchtigkeitsschäden sichtbar" in content

    def test_items_grouped_by_category(self):
        inspector, inspection = self._setup_in_progress()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Allgemeiner Eindruck" in content
        assert "Küche" in content
        assert "Badezimmer" in content

    def test_shows_progress_info(self):
        """Should display overall progress information."""
        inspector, inspection = self._setup_in_progress()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        content = response.content.decode()
        # Should show the apartment address
        assert inspection.apartment.street in content

    def test_requires_authentication(self):
        client = Client()
        inspector = InspectorFactory()
        _, inspection = self._setup_in_progress(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 302

    def test_requires_inspector_role(self):
        owner = OwnerFactory()
        inspector, inspection = self._setup_in_progress()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_other_inspector_gets_404(self):
        inspector1, inspection = self._setup_in_progress()
        inspector2 = InspectorFactory()
        client = Client()
        client.force_login(inspector2)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_scheduled_inspection_returns_404(self):
        """Cannot execute an inspection that hasn't been started."""
        inspector = InspectorFactory()
        inspection = _create_inspection_with_template(inspector, status=Inspection.Status.SCHEDULED)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_shows_ok_flag_na_buttons(self):
        """Each item should have OK, Flag, N/A tap targets."""
        inspector, inspection = self._setup_in_progress()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "OK" in content
        assert "N/A" in content

    def test_context_contains_grouped_items(self):
        inspector, inspection = self._setup_in_progress()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert "grouped_items" in response.context
        assert "inspection" in response.context

    def test_handles_german_characters(self):
        """Items with German umlauts should display correctly."""
        inspector = InspectorFactory()
        apt = ApartmentFactory(street="Währinger Straße")
        SubscriptionFactory(owner=apt.owner)
        ChecklistTemplateFactory(
            apartment=apt,
            items=[
                {
                    "category": "Küche",
                    "label": "Kühlschrank überprüfen",
                    "allowed_results": ["ok", "flagged"],
                    "order": 1,
                },
            ],
        )
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=_tomorrow_at(),
            scheduled_end=_tomorrow_at() + datetime.timedelta(hours=2),
            status=Inspection.Status.IN_PROGRESS,
        )
        InspectionItemFactory(
            inspection=inspection,
            checklist_label="Kühlschrank überprüfen",
            category="Küche",
            order=1,
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Kühlschrank überprüfen" in content
        assert "Küche" in content


# --- Update Item (HTMX) ---


@pytest.mark.django_db
class TestUpdateItemView:
    def _setup_item(self):
        """Create an in-progress inspection with an item."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.IN_PROGRESS,
        )
        item = InspectionItemFactory(
            inspection=inspection,
            checklist_label="Herd sauber",
            category="Küche",
            result=InspectionItem.Result.OK,
            severity=InspectionItem.Severity.NONE,
            order=1,
        )
        return inspector, inspection, item

    def test_update_result_to_ok(self):
        inspector, inspection, item = self._setup_item()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "ok"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.result == InspectionItem.Result.OK

    def test_update_result_to_flagged(self):
        inspector, inspection, item = self._setup_item()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(
            url,
            {"result": "flagged", "severity": "medium", "notes": "Herd ist schmutzig"},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.result == InspectionItem.Result.FLAGGED
        assert item.severity == InspectionItem.Severity.MEDIUM
        assert item.notes == "Herd ist schmutzig"

    def test_update_result_to_na(self):
        inspector, inspection, item = self._setup_item()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "na"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.result == InspectionItem.Result.NA

    def test_update_clears_severity_when_not_flagged(self):
        """When changing from flagged to OK, severity and notes should be cleared."""
        inspector, inspection, item = self._setup_item()
        item.result = InspectionItem.Result.FLAGGED
        item.severity = InspectionItem.Severity.HIGH
        item.notes = "Something wrong"
        item.save()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "ok"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.result == InspectionItem.Result.OK
        assert item.severity == InspectionItem.Severity.NONE
        assert item.notes == ""

    def test_update_returns_html_partial(self):
        """HTMX response should contain the updated item HTML."""
        inspector, inspection, item = self._setup_item()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "flagged", "severity": "low"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Herd sauber" in content

    def test_update_requires_authentication(self):
        _, _, item = self._setup_item()
        client = Client()
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "ok"})
        assert response.status_code == 302

    def test_update_requires_inspector_role(self):
        _, _, item = self._setup_item()
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "ok"})
        assert response.status_code == 404

    def test_update_other_inspector_gets_404(self):
        _, _, item = self._setup_item()
        other_inspector = InspectorFactory()
        client = Client()
        client.force_login(other_inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "ok"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_update_invalid_result_rejected(self):
        inspector, _, item = self._setup_item()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "invalid"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 400

    def test_update_requires_post(self):
        inspector, _, item = self._setup_item()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 405

    def test_update_completed_inspection_returns_404(self):
        """Cannot update items on a completed inspection."""
        inspector, inspection, item = self._setup_item()
        inspection.status = Inspection.Status.COMPLETED
        inspection.save(update_fields=["status"])
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_item", args=[item.pk])
        response = client.post(url, {"result": "flagged"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404


# --- Update General Notes (HTMX) ---


@pytest.mark.django_db
class TestUpdateGeneralNotesView:
    def _setup_inspection(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.IN_PROGRESS,
        )
        return inspector, inspection

    def test_update_general_notes(self):
        inspector, inspection = self._setup_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_general_notes", args=[inspection.pk])
        response = client.post(
            url,
            {"general_notes": "Alles in Ordnung, Wohnung sauber."},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        inspection.refresh_from_db()
        assert inspection.general_notes == "Alles in Ordnung, Wohnung sauber."

    def test_update_notes_requires_authentication(self):
        _, inspection = self._setup_inspection()
        client = Client()
        url = reverse("inspections:update_general_notes", args=[inspection.pk])
        response = client.post(url, {"general_notes": "test"})
        assert response.status_code == 302

    def test_update_notes_other_inspector_404(self):
        _, inspection = self._setup_inspection()
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:update_general_notes", args=[inspection.pk])
        response = client.post(url, {"general_notes": "test"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_update_notes_requires_post(self):
        inspector, inspection = self._setup_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_general_notes", args=[inspection.pk])
        response = client.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 405

    def test_update_notes_handles_german_text(self):
        inspector, inspection = self._setup_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_general_notes", args=[inspection.pk])
        notes = "Wohnung in Währing überprüft. Schäden an Küchentür festgestellt."
        response = client.post(url, {"general_notes": notes}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        inspection.refresh_from_db()
        assert inspection.general_notes == notes
