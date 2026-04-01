"""Tests for Report model."""

import pytest
from django.db import IntegrityError

from apps.inspections.models import Inspection
from apps.reports.models import Report
from tests.factories import InspectionFactory, ReportFactory


@pytest.mark.django_db
class TestReportCreate:
    def test_create_report(self):
        report = ReportFactory()
        assert report.pk is not None
        assert report.status == Report.Status.COMPLETED
        assert report.html_content
        assert report.generated_at is not None

    def test_create_pending_report(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        report = Report.objects.create(inspection=inspection)
        assert report.status == Report.Status.PENDING
        assert report.html_content == ""
        assert report.generated_at is None

    def test_default_status_is_pending(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        report = Report(inspection=inspection)
        assert report.status == Report.Status.PENDING


@pytest.mark.django_db
class TestReportStr:
    def test_str_representation(self):
        report = ReportFactory()
        result = str(report)
        assert "Report #" in result
        assert report.inspection.apartment.address in result
        assert "Fertig" in result

    def test_str_pending(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        report = Report.objects.create(inspection=inspection)
        assert "Ausstehend" in str(report)


@pytest.mark.django_db
class TestReportConstraints:
    def test_one_report_per_inspection(self):
        """Each inspection can have exactly one report (OneToOneField)."""
        report = ReportFactory()
        with pytest.raises(IntegrityError):
            Report.objects.create(inspection=report.inspection)

    def test_cascade_delete_with_inspection(self):
        report = ReportFactory()
        inspection_pk = report.inspection.pk
        report.inspection.delete()
        assert not Report.objects.filter(inspection_id=inspection_pk).exists()

    def test_status_choices(self):
        assert Report.Status.PENDING == "pending"
        assert Report.Status.GENERATING == "generating"
        assert Report.Status.COMPLETED == "completed"
        assert Report.Status.FAILED == "failed"

    def test_html_content_blank_allowed(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        report = Report.objects.create(inspection=inspection, html_content="")
        assert report.html_content == ""

    def test_error_message_blank_allowed(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        report = Report.objects.create(inspection=inspection, status=Report.Status.FAILED, error_message="")
        assert report.error_message == ""


@pytest.mark.django_db
class TestReportRelationships:
    def test_inspection_has_report(self):
        report = ReportFactory()
        assert report.inspection.report == report

    def test_report_accesses_apartment(self):
        report = ReportFactory()
        assert report.inspection.apartment is not None
        assert report.inspection.apartment.address

    def test_report_accesses_inspector(self):
        report = ReportFactory()
        assert report.inspection.inspector is not None

    def test_report_accesses_owner(self):
        report = ReportFactory()
        assert report.inspection.apartment.owner is not None


@pytest.mark.django_db
class TestReportBusinessLogic:
    def test_is_ready_when_completed_with_content(self):
        report = ReportFactory(status=Report.Status.COMPLETED, html_content="<h1>Report</h1>")
        assert report.is_ready is True

    def test_is_not_ready_when_pending(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        report = Report.objects.create(inspection=inspection)
        assert report.is_ready is False

    def test_is_not_ready_when_generating(self):
        report = ReportFactory(status=Report.Status.GENERATING, html_content="")
        assert report.is_ready is False

    def test_is_not_ready_when_failed(self):
        report = ReportFactory(status=Report.Status.FAILED, html_content="")
        assert report.is_ready is False

    def test_is_not_ready_when_completed_but_empty_content(self):
        report = ReportFactory(status=Report.Status.COMPLETED, html_content="")
        assert report.is_ready is False

    def test_overall_rating_delegates_to_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.ATTENTION,
        )
        report = ReportFactory(inspection=inspection)
        assert report.overall_rating == "attention"

    def test_overall_rating_display_delegates_to_inspection(self):
        inspection = InspectionFactory(
            status=Inspection.Status.COMPLETED,
            overall_rating=Inspection.OverallRating.URGENT,
        )
        report = ReportFactory(inspection=inspection)
        assert report.overall_rating_display == "Dringend"

    def test_ordering_by_created_at_desc(self):
        r1 = ReportFactory()
        r2 = ReportFactory()
        reports = list(Report.objects.all())
        assert reports[0] == r2
        assert reports[1] == r1

    def test_timestamps_auto_set(self):
        report = ReportFactory()
        assert report.created_at is not None
        assert report.updated_at is not None
