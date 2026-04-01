"""Tests for report admin actions."""

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.reports.models import Report
from tests.factories import AdminFactory, ReportFactory


@pytest.mark.django_db
class TestResendReportEmailAction:
    def test_resend_clears_email_sent_at_and_queues_task(self):
        admin_user = AdminFactory(is_staff=True, is_superuser=True)
        report = ReportFactory(status=Report.Status.COMPLETED, email_sent_at=timezone.now())

        client = Client()
        client.force_login(admin_user)

        url = reverse("admin:reports_report_changelist")
        with patch("apps.reports.admin.queue_task") as mock_queue:
            response = client.post(
                url,
                {
                    "action": "resend_report_email",
                    "_selected_action": [report.pk],
                },
            )
        assert response.status_code == 302

        report.refresh_from_db()
        assert report.email_sent_at is None
        mock_queue.assert_called_once()

    def test_resend_skips_non_completed_reports(self):
        admin_user = AdminFactory(is_staff=True, is_superuser=True)
        report = ReportFactory(status=Report.Status.FAILED, html_content="", generated_at=None)

        client = Client()
        client.force_login(admin_user)

        url = reverse("admin:reports_report_changelist")
        with patch("apps.reports.admin.queue_task") as mock_queue:
            client.post(
                url,
                {
                    "action": "resend_report_email",
                    "_selected_action": [report.pk],
                },
            )
        mock_queue.assert_not_called()
