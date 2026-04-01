"""Tests for inspection email tasks — urgent notification, reminders."""

import datetime

import pytest
from django.core import mail
from django.utils import timezone

from apps.inspections.models import Inspection
from apps.inspections.tasks import send_inspection_reminder, send_owner_reminder, send_urgent_notification
from tests.factories import InspectionFactory, InspectionItemFactory


@pytest.mark.django_db
class TestSendUrgentNotification:
    def test_sends_email_for_urgent_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.URGENT,
            completed_at=timezone.now(),
        )
        InspectionItemFactory(inspection=inspection, result="flagged", severity="high", notes="Wasserschaden")

        result = send_urgent_notification(inspection.pk)

        assert result["status"] == "sent"
        assert result["owner_email"] == inspection.apartment.owner.email
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert "Dringend" in email.subject
        assert inspection.apartment.address in email.subject
        assert email.to == [inspection.apartment.owner.email]
        assert len(email.alternatives) == 1  # HTML version

    def test_skips_non_urgent_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.OK,
        )
        result = send_urgent_notification(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_urgent"
        assert len(mail.outbox) == 0

    def test_skips_attention_rating(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.ATTENTION,
        )
        result = send_urgent_notification(inspection.pk)
        assert result["status"] == "skipped"
        assert len(mail.outbox) == 0

    def test_skips_non_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.SCHEDULED)
        result = send_urgent_notification(inspection.pk)
        assert result["status"] == "skipped"
        assert len(mail.outbox) == 0

    def test_email_includes_flagged_items(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.URGENT,
            completed_at=timezone.now(),
        )
        InspectionItemFactory(
            inspection=inspection,
            result="flagged",
            severity="high",
            checklist_label="Rohrleitungsbruch",
            notes="Wasser im Keller",
        )

        send_urgent_notification(inspection.pk)

        email = mail.outbox[0]
        html_body = email.alternatives[0][0]
        assert "Rohrleitungsbruch" in html_body
        assert "Wasser im Keller" in html_body

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_urgent_notification(999999)


@pytest.mark.django_db
class TestSendOwnerReminder:
    def test_sends_email_for_scheduled_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        result = send_owner_reminder(inspection.pk)

        assert result["status"] == "sent"
        assert result["owner_email"] == inspection.apartment.owner.email
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert "morgen" in email.subject or "Inspektion" in email.subject
        assert inspection.apartment.address in email.subject
        assert email.to == [inspection.apartment.owner.email]
        assert len(email.alternatives) == 1

    def test_skips_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        result = send_owner_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert len(mail.outbox) == 0

    def test_skips_cancelled_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.CANCELLED)
        result = send_owner_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert len(mail.outbox) == 0

    def test_email_contains_address_and_time(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        send_owner_reminder(inspection.pk)

        email = mail.outbox[0]
        assert inspection.apartment.address in email.body
        html_body = email.alternatives[0][0]
        assert inspection.apartment.address in html_body

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_owner_reminder(999999)


@pytest.mark.django_db
class TestSendInspectionReminder:
    def test_sends_email_to_inspector(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(hours=2),
        )
        result = send_inspection_reminder(inspection.pk)

        assert result["status"] == "sent"
        assert result["inspector_email"] == inspection.inspector.email
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [inspection.inspector.email]
        assert inspection.apartment.address in email.subject
        assert len(email.alternatives) == 1

    def test_skips_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert len(mail.outbox) == 0

    def test_skips_cancelled_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.CANCELLED)
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert len(mail.outbox) == 0

    def test_skips_past_due_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() - datetime.timedelta(hours=1),
        )
        result = send_inspection_reminder(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "past_due"
        assert len(mail.outbox) == 0

    def test_email_has_plain_text_and_html(self):
        inspection = InspectionFactory(
            status=Inspection.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(hours=2),
        )
        send_inspection_reminder(inspection.pk)

        email = mail.outbox[0]
        assert email.body  # plain text
        html_body, content_type = email.alternatives[0]
        assert content_type == "text/html"
        assert inspection.apartment.address in html_body

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_inspection_reminder(999999)
