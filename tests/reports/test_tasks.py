"""Tests for report background tasks."""

import pytest

from apps.inspections.models import Inspection
from apps.reports.tasks import generate_report, send_report_email
from tests.factories import InspectionFactory


@pytest.mark.django_db
class TestGenerateReport:
    def test_skips_non_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.SCHEDULED)
        result = generate_report(inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_completed"

    def test_processes_completed_inspection(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        result = generate_report(inspection.pk)
        assert result["inspection_id"] == inspection.pk
        assert result["status"] == "pending_implementation"

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
class TestSendReportEmail:
    def test_returns_owner_email(self):
        inspection = InspectionFactory()
        result = send_report_email(inspection.pk)
        assert result["owner_email"] == inspection.apartment.owner.email
        assert result["inspection_id"] == inspection.pk

    def test_raises_for_nonexistent_inspection(self):
        with pytest.raises(Inspection.DoesNotExist):
            send_report_email(999999)
