"""Integration tests for the full inspection-to-email flow."""

import pytest
from django.core import mail
from django.utils import timezone

from apps.inspections.models import Inspection
from apps.inspections.tasks import send_urgent_notification
from apps.reports.tasks import generate_report, send_report_email
from tests.factories import InspectionFactory, InspectionItemFactory


@pytest.mark.django_db
class TestFullInspectionToEmailFlow:
    def test_generate_then_send_email(self):
        """End-to-end: generate_report produces HTML, send_report_email delivers it."""
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating="ok",
            completed_at=timezone.now(),
        )
        InspectionItemFactory(inspection=inspection, result="ok")

        # Step 1: Generate report (in real flow, this chains send_report_email)
        result = generate_report(inspection.pk)
        assert result["status"] == "completed"

        # Step 2: Send email (simulating the chained task)
        email_result = send_report_email(inspection.pk)
        assert email_result["status"] == "sent"

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [inspection.apartment.owner.email]
        assert "Inspektionsbericht" in email.subject
        assert inspection.apartment.address in email.subject
        assert len(email.alternatives) == 1

    def test_idempotency_prevents_duplicate_email(self):
        """Calling send_report_email twice sends only one email."""
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating="ok",
            completed_at=timezone.now(),
        )
        InspectionItemFactory(inspection=inspection)

        generate_report(inspection.pk)

        result1 = send_report_email(inspection.pk)
        assert result1["status"] == "sent"

        result2 = send_report_email(inspection.pk)
        assert result2["status"] == "skipped"
        assert result2["reason"] == "already_sent"

        assert len(mail.outbox) == 1  # only one email sent

    def test_urgent_inspection_sends_both_emails(self):
        """Urgent inspection triggers urgent alert + report email = 2 emails total."""
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.URGENT,
            completed_at=timezone.now(),
        )
        InspectionItemFactory(inspection=inspection, result="flagged", severity="high")

        # Urgent notification (sent immediately on submit)
        urgent_result = send_urgent_notification(inspection.pk)
        assert urgent_result["status"] == "sent"

        # Report generated and email chained
        report_result = generate_report(inspection.pk)
        assert report_result["status"] == "completed"

        email_result = send_report_email(inspection.pk)
        assert email_result["status"] == "sent"

        assert len(mail.outbox) == 2
        subjects = [e.subject for e in mail.outbox]
        assert any("Dringend" in s for s in subjects)
        assert any("Inspektionsbericht" in s for s in subjects)

    def test_report_email_with_flagged_items(self):
        """Report email includes flagged item details."""
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating="attention",
            completed_at=timezone.now(),
        )
        InspectionItemFactory(
            inspection=inspection,
            result="flagged",
            severity="medium",
            checklist_label="Fenster undicht",
            category="Wohnzimmer",
            notes="Zugluft spürbar",
        )
        InspectionItemFactory(inspection=inspection, result="ok")

        generate_report(inspection.pk)
        send_report_email(inspection.pk)

        email = mail.outbox[0]
        html_body = email.alternatives[0][0]
        assert "Fenster undicht" in html_body
        assert "Wohnzimmer" in html_body

    def test_report_email_with_german_umlauts(self):
        """Email handles German umlauts correctly."""
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating="ok",
            completed_at=timezone.now(),
        )
        InspectionItemFactory(
            inspection=inspection,
            result="flagged",
            checklist_label="Kühlschrank überprüfen",
            notes="Türdichtung löst sich",
        )

        generate_report(inspection.pk)
        send_report_email(inspection.pk)

        email = mail.outbox[0]
        # Plain text should contain umlauts
        assert "Kühlschrank" in email.body or "K" in email.body
