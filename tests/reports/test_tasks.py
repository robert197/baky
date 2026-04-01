"""Tests for report background tasks."""

from unittest.mock import patch

import pytest

from apps.inspections.models import Inspection, InspectionItem
from apps.reports.models import Report
from apps.reports.tasks import generate_report, send_report_email
from tests.factories import InspectionFactory, InspectionItemFactory, PhotoFactory, ReportFactory


@pytest.mark.django_db
class TestGenerateReportSkipCases:
    def test_skips_non_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.SCHEDULED)
        result = generate_report(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_completed"

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            generate_report(999999)

    def test_skips_cancelled_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.CANCELLED)
        result = generate_report(inspection.pk)
        assert result["status"] == "skipped"

    def test_skips_in_progress_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.IN_PROGRESS)
        result = generate_report(inspection.pk)
        assert result["status"] == "skipped"


@pytest.mark.django_db
class TestGenerateReportImplementation:
    def test_creates_report_for_completed_inspection(self):
        """generate_report creates a Report with COMPLETED status and non-empty html_content."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection, category="Eingang", result=InspectionItem.Result.OK)
        InspectionItemFactory(
            inspection=inspection,
            category="Küche",
            result=InspectionItem.Result.FLAGGED,
            severity=InspectionItem.Severity.MEDIUM,
            notes="Herd verschmutzt",
        )

        result = generate_report(inspection.pk)

        assert result["status"] == "completed"
        report = Report.objects.get(inspection=inspection)
        assert report.status == Report.Status.COMPLETED
        assert report.html_content
        assert report.generated_at is not None
        assert "Eingang" in report.html_content
        assert "Küche" in report.html_content

    def test_report_html_contains_apartment_address(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert inspection.apartment.address in report.html_content

    def test_report_html_contains_overall_rating(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating=Inspection.OverallRating.OK)
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "OK" in report.html_content

    def test_report_groups_items_by_category(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection, category="Eingang", order=1)
        InspectionItemFactory(inspection=inspection, category="Küche", order=2)
        InspectionItemFactory(inspection=inspection, category="Eingang", order=3)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        # Both Eingang items should be grouped together — Eingang first (lower min order)
        eingang_pos = report.html_content.index("Eingang")
        kuche_pos = report.html_content.index("Küche")
        assert eingang_pos < kuche_pos

    def test_report_with_no_items(self):
        """Report should still generate even with no checklist items."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        result = generate_report(inspection.pk)
        assert result["status"] == "completed"
        report = Report.objects.get(inspection=inspection)
        assert report.status == Report.Status.COMPLETED


@pytest.mark.django_db
class TestGenerateReportErrorHandling:
    def test_sets_failed_status_on_template_error(self):
        """If rendering fails, report status should be FAILED with error_message."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection)
        with patch("apps.reports.tasks.render_to_string", side_effect=Exception("Template error")):
            result = generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert report.status == Report.Status.FAILED
        assert "Template error" in report.error_message
        assert result["status"] == "failed"

    def test_skips_already_completed_report(self):
        """Idempotent: if report already completed, skip without error."""
        report = ReportFactory(status=Report.Status.COMPLETED)
        result = generate_report(report.inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_completed"

    def test_regenerates_failed_report(self):
        """A failed report should be regenerated on retry."""
        report = ReportFactory(status=Report.Status.FAILED, html_content="", generated_at=None)
        InspectionItemFactory(inspection=report.inspection)
        result = generate_report(report.inspection.pk)
        report.refresh_from_db()
        assert report.status == Report.Status.COMPLETED
        assert report.html_content
        assert result["status"] == "completed"

    def test_regenerates_pending_report(self):
        """A pending report (from crash) should be regenerated."""
        report = ReportFactory(status=Report.Status.PENDING, html_content="", generated_at=None)
        InspectionItemFactory(inspection=report.inspection)
        generate_report(report.inspection.pk)
        report.refresh_from_db()
        assert report.status == Report.Status.COMPLETED


@pytest.mark.django_db
class TestReportTemplateRendering:
    def test_renders_flagged_items_with_severity_badge(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="attention")
        InspectionItemFactory(
            inspection=inspection,
            result=InspectionItem.Result.FLAGGED,
            severity=InspectionItem.Severity.HIGH,
            notes="Schimmel entdeckt",
        )
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Schimmel entdeckt" in report.html_content
        assert "Hoch" in report.html_content

    def test_renders_ok_items_in_compact_format(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(
            inspection=inspection, result=InspectionItem.Result.OK, checklist_label="Tür schließt korrekt"
        )
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Tür schließt korrekt" in report.html_content

    def test_renders_na_items(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection, result=InspectionItem.Result.NA, checklist_label="Gaskontrolle")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Gaskontrolle" in report.html_content
        assert "N/A" in report.html_content

    def test_renders_inspector_general_notes(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating="ok",
            general_notes="Alles in Ordnung, sehr gepflegt.",
        )
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Alles in Ordnung, sehr gepflegt." in report.html_content

    def test_renders_with_german_umlauts(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(
            inspection=inspection,
            category="Küche",
            checklist_label="Kühlschrank überprüfen",
            notes="Türdichtung löst sich",
            result=InspectionItem.Result.FLAGGED,
            severity=InspectionItem.Severity.LOW,
        )
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Kühlschrank überprüfen" in report.html_content
        assert "Türdichtung löst sich" in report.html_content

    def test_html_is_self_contained(self):
        """Report HTML should be a complete document — not extending a base template."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "<!DOCTYPE html>" in report.html_content

    def test_escapes_user_content(self):
        """XSS prevention: user-generated content must be escaped."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(
            inspection=inspection,
            notes='<script>alert("xss")</script>',
            result=InspectionItem.Result.FLAGGED,
            severity=InspectionItem.Severity.LOW,
        )
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "<script>" not in report.html_content
        assert "&lt;script&gt;" in report.html_content

    def test_renders_photos_with_proxy_urls(self):
        """Photos should be referenced via /reports/photos/<id>/ proxy URL."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        item = InspectionItemFactory(inspection=inspection)
        photo = PhotoFactory(inspection=inspection, inspection_item=item, caption="Testfoto")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert f"/reports/photos/{photo.pk}/" in report.html_content

    def test_renders_photo_gallery_section(self):
        """All inspection photos should appear in a photo gallery."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection)
        PhotoFactory(inspection=inspection, caption="Foto 1")
        PhotoFactory(inspection=inspection, caption="Foto 2")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Foto 1" in report.html_content
        assert "Foto 2" in report.html_content


@pytest.mark.django_db
class TestSendReportEmail:
    def test_returns_owner_email(self):
        inspection = InspectionFactory()
        result = send_report_email(inspection.pk)
        assert result["owner_email"] == inspection.apartment.owner.email
        assert result["inspection_id"] == inspection.pk

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_report_email(999999)
