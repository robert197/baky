"""Tests for inspection background tasks."""

import datetime

import pytest
from django.utils import timezone

from apps.inspections.models import Inspection
from apps.inspections.tasks import generate_thumbnail, send_inspection_reminder
from tests.factories import InspectionFactory, PhotoFactory


@pytest.mark.django_db
class TestGenerateThumbnail:
    def test_skips_photo_with_existing_thumbnail(self):
        photo = PhotoFactory()
        # PhotoFactory auto-generates a thumbnail via Photo.save()
        assert photo.thumbnail
        result = generate_thumbnail(photo.pk)
        assert result["status"] == "already_exists"

    def test_raises_for_nonexistent_photo(self):
        from apps.inspections.models import Photo

        with pytest.raises(Photo.DoesNotExist):
            generate_thumbnail(999999)


@pytest.mark.django_db
class TestSendInspectionReminder:
    def test_sends_reminder_for_scheduled_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(hours=2),
        )
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "sent"
        assert result["inspector_email"] == inspection.inspector.email

    def test_skips_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == Inspection.Status.COMPLETED

    def test_skips_cancelled_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.CANCELLED)
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == Inspection.Status.CANCELLED

    def test_skips_past_due_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() - datetime.timedelta(hours=1),
        )
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "past_due"

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_inspection_reminder(999999)
