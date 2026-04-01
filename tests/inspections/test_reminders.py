"""Tests for the reminder system — management command and owner reminder task."""

import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.inspections.models import Inspection
from apps.inspections.tasks import send_owner_reminder
from tests.factories import ApartmentFactory, InspectionFactory, InspectorFactory, OwnerFactory


@pytest.mark.django_db
class TestSendInspectionRemindersCommand:
    def test_queues_reminders_for_tomorrows_inspections(self):
        tomorrow = (timezone.localtime(timezone.now()) + datetime.timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        InspectionFactory(
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.SCHEDULED,
        )
        out = StringIO()
        with patch("apps.inspections.management.commands.send_inspection_reminders.queue_task") as mock_queue:
            call_command("send_inspection_reminders", stdout=out)
        # Should queue 2 tasks: one for inspector, one for owner
        assert mock_queue.call_count == 2
        assert "1 Erinnerung" in out.getvalue()

    def test_skips_non_scheduled_inspections(self):
        tomorrow = (timezone.localtime(timezone.now()) + datetime.timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        InspectionFactory(
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.CANCELLED,
        )
        out = StringIO()
        with patch("apps.inspections.management.commands.send_inspection_reminders.queue_task") as mock_queue:
            call_command("send_inspection_reminders", stdout=out)
        assert mock_queue.call_count == 0
        assert "0 Erinnerung" in out.getvalue()

    def test_skips_inspections_not_tomorrow(self):
        day_after = (timezone.localtime(timezone.now()) + datetime.timedelta(days=2)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        InspectionFactory(
            scheduled_at=day_after,
            scheduled_end=day_after + datetime.timedelta(hours=2),
            status=Inspection.Status.SCHEDULED,
        )
        out = StringIO()
        with patch("apps.inspections.management.commands.send_inspection_reminders.queue_task") as mock_queue:
            call_command("send_inspection_reminders", stdout=out)
        assert mock_queue.call_count == 0

    def test_multiple_inspections_queued(self):
        tomorrow = (timezone.localtime(timezone.now()) + datetime.timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        inspector = InspectorFactory()
        InspectionFactory(
            inspector=inspector,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.SCHEDULED,
        )
        InspectionFactory(
            scheduled_at=tomorrow.replace(hour=14),
            scheduled_end=tomorrow.replace(hour=16),
            status=Inspection.Status.SCHEDULED,
        )
        out = StringIO()
        with patch("apps.inspections.management.commands.send_inspection_reminders.queue_task") as mock_queue:
            call_command("send_inspection_reminders", stdout=out)
        # 2 inspections × 2 reminders each = 4 queued tasks
        assert mock_queue.call_count == 4
        assert "2 Erinnerung" in out.getvalue()


@pytest.mark.django_db
class TestSendOwnerReminder:
    def test_sends_for_scheduled_inspection(self):
        owner = OwnerFactory(email="owner@example.com")
        apt = ApartmentFactory(owner=owner)
        tomorrow = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        inspection = InspectionFactory(
            apartment=apt,
            scheduled_at=tomorrow,
            scheduled_end=tomorrow + datetime.timedelta(hours=2),
            status=Inspection.Status.SCHEDULED,
        )
        result = send_owner_reminder(inspection.pk)
        assert result["status"] == "sent"
        assert result["owner_email"] == "owner@example.com"

    def test_skips_cancelled_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.CANCELLED)
        result = send_owner_reminder(inspection.pk)
        assert result["status"] == "skipped"

    def test_skips_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        result = send_owner_reminder(inspection.pk)
        assert result["status"] == "skipped"

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_owner_reminder(999999)
