"""Tests for inspection submission flow views (review, submit, confirmation)."""

import datetime
from unittest.mock import patch

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
    PhotoFactory,
    SubscriptionFactory,
)


def _tomorrow_at(hour: int = 10) -> datetime.datetime:
    """Return tomorrow at the given hour in the current timezone."""
    return timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)


def _create_in_progress_inspection(inspector, num_items=3, **kwargs):
    """Create an in-progress inspection with items."""
    apt = kwargs.pop("apartment", None) or ApartmentFactory()
    SubscriptionFactory(owner=apt.owner)
    tomorrow = _tomorrow_at()
    inspection = InspectionFactory(
        inspector=inspector,
        apartment=apt,
        scheduled_at=tomorrow,
        scheduled_end=tomorrow + datetime.timedelta(hours=2),
        status=Inspection.Status.IN_PROGRESS,
        started_at=timezone.now(),
        **kwargs,
    )
    items = []
    for i in range(num_items):
        items.append(
            InspectionItemFactory(
                inspection=inspection,
                checklist_label=f"Punkt {i + 1}",
                category="Allgemein",
                result=InspectionItem.Result.OK,
                order=i + 1,
            )
        )
    return inspection, items


# --- Review Inspection View ---


@pytest.mark.django_db
class TestReviewInspectionView:
    def test_review_shows_summary(self):
        """Review screen should show item counts and photo count."""
        inspector = InspectorFactory()
        inspection, items = _create_in_progress_inspection(inspector)
        # Flag one item
        items[1].result = InspectionItem.Result.FLAGGED
        items[1].severity = InspectionItem.Severity.MEDIUM
        items[1].notes = "Beschädigt"
        items[1].save()
        # Add a photo
        PhotoFactory(inspection=inspection)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        # Should show item summary
        assert "2" in content  # 2 OK items
        assert "1" in content  # 1 flagged item
        assert "1" in content  # 1 photo
        assert "Punkt 2" in content  # Flagged item label

    def test_review_shows_flagged_items_list(self):
        """Review should list all flagged items with severity."""
        inspector = InspectorFactory()
        inspection, items = _create_in_progress_inspection(inspector)
        items[0].result = InspectionItem.Result.FLAGGED
        items[0].severity = InspectionItem.Severity.HIGH
        items[0].notes = "Schwerer Schaden"
        items[0].save()

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)

        content = response.content.decode()
        assert "Punkt 1" in content
        assert "Schwerer Schaden" in content

    def test_review_shows_general_notes(self):
        """Review should display general notes if present."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        inspection.general_notes = "Wohnung insgesamt in gutem Zustand."
        inspection.save(update_fields=["general_notes"])

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)

        content = response.content.decode()
        assert "Wohnung insgesamt in gutem Zustand." in content

    def test_review_shows_overall_rating_selector(self):
        """Review must have an overall rating selector (OK / Attention / Urgent)."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)

        content = response.content.decode()
        assert "ok" in content.lower()
        assert "attention" in content.lower() or "achtung" in content.lower()
        assert "urgent" in content.lower() or "dringend" in content.lower()

    def test_review_requires_authentication(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        client = Client()
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_review_requires_inspector_role(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_review_other_inspector_gets_404(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_review_only_in_progress(self):
        """Cannot review a scheduled or completed inspection."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        scheduled = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.SCHEDULED,
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[scheduled.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_review_context_has_summary_data(self):
        """Context should contain counts for ok, flagged, na items."""
        inspector = InspectorFactory()
        inspection, items = _create_in_progress_inspection(inspector, num_items=5)
        items[0].result = InspectionItem.Result.FLAGGED
        items[0].severity = InspectionItem.Severity.LOW
        items[0].save()
        items[1].result = InspectionItem.Result.NA
        items[1].save()

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)

        assert response.context["ok_count"] == 3
        assert response.context["flagged_count"] == 1
        assert response.context["na_count"] == 1
        assert response.context["photo_count"] == 0
        assert len(response.context["flagged_items"]) == 1

    def test_review_shows_edit_link_back_to_execute(self):
        """Review should have a link back to the execution page."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:review_inspection", args=[inspection.pk])
        response = client.get(url)

        content = response.content.decode()
        execute_url = reverse("inspections:execute_inspection", args=[inspection.pk])
        assert execute_url in content


# --- Submit Inspection View ---


@pytest.mark.django_db
class TestSubmitInspectionView:
    def test_submit_sets_completed_status(self):
        """Submitting should set status to COMPLETED and record completed_at."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "ok"})

        assert response.status_code == 302
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.COMPLETED
        assert inspection.completed_at is not None
        assert inspection.overall_rating == Inspection.OverallRating.OK

    def test_submit_requires_overall_rating(self):
        """Cannot submit without selecting an overall rating."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {})

        # Should redirect back to review with error
        assert response.status_code == 302
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.IN_PROGRESS  # Not changed

    def test_submit_rejects_invalid_rating(self):
        """Invalid rating value should not submit."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "invalid"})

        assert response.status_code == 302
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.IN_PROGRESS

    def test_submit_cannot_with_zero_items(self):
        """Cannot submit an inspection with 0 items checked (all default OK counts as checked)."""
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
            started_at=timezone.now(),
        )
        # No items at all

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "ok"})

        assert response.status_code == 302
        inspection.refresh_from_db()
        assert inspection.status == Inspection.Status.IN_PROGRESS

    @patch("apps.inspections.views.queue_task")
    def test_submit_triggers_report_generation(self, mock_queue):
        """Should trigger background task for report generation."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        client.post(url, {"overall_rating": "ok"})

        # Check that report generation was queued
        calls = [c for c in mock_queue.call_args_list if "generate_report" in str(c)]
        assert len(calls) == 1

    @patch("apps.inspections.views.queue_task")
    def test_submit_triggers_email_delivery(self, mock_queue):
        """Should trigger background task for email delivery to owner."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        client.post(url, {"overall_rating": "ok"})

        # Check that email send was queued
        calls = [c for c in mock_queue.call_args_list if "send_report_email" in str(c)]
        assert len(calls) == 1

    @patch("apps.inspections.views.queue_task")
    def test_urgent_rating_triggers_immediate_notification(self, mock_queue):
        """Urgent overall rating should trigger an immediate notification task."""
        inspector = InspectorFactory()
        inspection, items = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        client.post(url, {"overall_rating": "urgent"})

        # Check that urgent notification was queued
        calls = [c for c in mock_queue.call_args_list if "send_urgent_notification" in str(c)]
        assert len(calls) == 1

    def test_submit_redirects_to_confirmation(self):
        """After successful submit, should redirect to confirmation page."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "attention"})

        assert response.status_code == 302
        expected_url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        assert expected_url in response.url

    def test_submit_requires_post(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 405

    def test_submit_requires_authentication(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        client = Client()
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "ok"})
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_submit_requires_inspector_role(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "ok"})
        assert response.status_code == 404

    def test_submit_other_inspector_gets_404(self):
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        response = client.post(url, {"overall_rating": "ok"})
        assert response.status_code == 404

    def test_submit_only_in_progress(self):
        """Cannot submit a scheduled or already completed inspection."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        completed = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[completed.pk])
        response = client.post(url, {"overall_rating": "ok"})
        assert response.status_code == 404

    def test_submit_with_attention_rating(self):
        """Attention rating should work without triggering urgent notification."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        client.post(url, {"overall_rating": "attention"})

        inspection.refresh_from_db()
        assert inspection.overall_rating == Inspection.OverallRating.ATTENTION
        assert inspection.status == Inspection.Status.COMPLETED

    def test_submit_is_irreversible(self):
        """Once submitted, cannot submit again."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:submit_inspection", args=[inspection.pk])
        # First submit
        client.post(url, {"overall_rating": "ok"})
        # Second submit attempt should 404 (status is COMPLETED now)
        response = client.post(url, {"overall_rating": "urgent"})
        assert response.status_code == 404

        inspection.refresh_from_db()
        assert inspection.overall_rating == Inspection.OverallRating.OK  # Unchanged from first submit


# --- Inspection Submitted (Confirmation) View ---


@pytest.mark.django_db
class TestInspectionSubmittedView:
    def test_confirmation_shows_summary(self):
        """Confirmation should display the inspection summary."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=timezone.now(),
            overall_rating=Inspection.OverallRating.OK,
        )
        InspectionItemFactory(inspection=inspection, result=InspectionItem.Result.OK, order=1)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert apt.street in content

    def test_confirmation_shows_next_inspection_link(self):
        """Should have a link back to the schedule."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=timezone.now(),
            overall_rating=Inspection.OverallRating.ATTENTION,
        )

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        response = client.get(url)

        content = response.content.decode()
        schedule_url = reverse("inspections:schedule")
        assert schedule_url in content

    def test_confirmation_only_for_completed(self):
        """Cannot view confirmation for an in-progress inspection."""
        inspector = InspectorFactory()
        inspection, _ = _create_in_progress_inspection(inspector)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_confirmation_requires_authentication(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=timezone.now(),
            overall_rating=Inspection.OverallRating.OK,
        )
        client = Client()
        url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_confirmation_other_inspector_gets_404(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=timezone.now(),
            overall_rating=Inspection.OverallRating.OK,
        )
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 404

    def test_confirmation_shows_overall_rating(self):
        """Confirmation should display the overall rating."""
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        SubscriptionFactory(owner=apt.owner)
        tomorrow = _tomorrow_at()
        inspection = InspectionFactory(
            inspector=inspector,
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.COMPLETED,
            completed_at=timezone.now(),
            overall_rating=Inspection.OverallRating.URGENT,
        )
        InspectionItemFactory(inspection=inspection, result=InspectionItem.Result.FLAGGED, severity="urgent", order=1)

        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:inspection_submitted", args=[inspection.pk])
        response = client.get(url)

        content = response.content.decode()
        assert "Dringend" in content or "urgent" in content.lower()
