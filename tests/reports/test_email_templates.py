"""Tests for email template rendering."""

import pytest
from django.template.loader import render_to_string

from tests.factories import InspectionFactory, InspectionItemFactory


@pytest.mark.django_db
class TestEmailBaseTemplate:
    def test_renders_with_content(self):
        html = render_to_string("emails/_base.html", {"content": "<p>Hello</p>"})
        assert "BAKY" in html
        assert "<table" in html

    def test_has_inline_styles(self):
        html = render_to_string("emails/_base.html", {"content": "<p>Test</p>"})
        assert 'style="' in html
        assert "#1e293b" in html  # primary color

    def test_contains_tagline(self):
        html = render_to_string("emails/_base.html", {})
        assert "Betreuung. Absicherung. Kontrolle. Your Home." in html


@pytest.mark.django_db
class TestReportEmailTemplate:
    def test_html_renders_with_inspection_data(self):
        inspection = InspectionFactory(status="completed", overall_rating="ok")
        html = render_to_string(
            "emails/report_email.html",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "report_url": "https://baky.at/reports/1/",
                "rating_display": "OK",
                "flagged_items": [],
            },
        )
        assert inspection.apartment.address in html
        assert "Inspektionsbericht" in html
        assert "https://baky.at/reports/1/" in html
        assert "OK" in html

    def test_txt_renders_with_inspection_data(self):
        inspection = InspectionFactory(status="completed", overall_rating="ok")
        txt = render_to_string(
            "emails/report_email.txt",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "report_url": "https://baky.at/reports/1/",
                "rating_display": "OK",
                "flagged_items": [],
            },
        )
        assert inspection.apartment.address in txt
        assert "https://baky.at/reports/1/" in txt

    def test_html_renders_flagged_items(self):
        inspection = InspectionFactory(status="completed", overall_rating="attention")
        item = InspectionItemFactory(
            inspection=inspection,
            result="flagged",
            checklist_label="Herd verschmutzt",
            category="Küche",
            notes="Starke Verschmutzung",
        )
        html = render_to_string(
            "emails/report_email.html",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "report_url": "https://baky.at/reports/1/",
                "rating_display": "Achtung",
                "flagged_items": [item],
            },
        )
        assert "Herd verschmutzt" in html
        assert "Küche" in html
        assert "Starke Verschmutzung" in html

    def test_html_no_flagged_items_message(self):
        inspection = InspectionFactory(status="completed", overall_rating="ok")
        html = render_to_string(
            "emails/report_email.html",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "report_url": "https://baky.at/reports/1/",
                "rating_display": "OK",
                "flagged_items": [],
            },
        )
        assert "Keine Auff" in html  # "Keine Auffälligkeiten"


@pytest.mark.django_db
class TestUrgentAlertTemplate:
    def test_html_renders_urgent_alert(self):
        inspection = InspectionFactory(status="completed", overall_rating="urgent")
        item = InspectionItemFactory(inspection=inspection, result="flagged", notes="Wasserrohrbruch")
        html = render_to_string(
            "emails/urgent_alert.html",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "flagged_items": [item],
                "report_url": "https://baky.at/reports/1/",
            },
        )
        assert "DRINGEND" in html
        assert inspection.apartment.address in html
        assert "Wasserrohrbruch" in html

    def test_txt_renders_urgent_alert(self):
        inspection = InspectionFactory(status="completed", overall_rating="urgent")
        txt = render_to_string(
            "emails/urgent_alert.txt",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "flagged_items": [],
                "report_url": "https://baky.at/reports/1/",
            },
        )
        assert "DRINGEND" in txt
        assert inspection.apartment.address in txt


@pytest.mark.django_db
class TestReminderTemplates:
    def test_owner_reminder_html_renders(self):
        inspection = InspectionFactory(status="scheduled")
        html = render_to_string(
            "emails/owner_reminder.html",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "scheduled_date": "02.04.2026",
                "scheduled_time": "10:00",
            },
        )
        assert inspection.apartment.address in html
        assert "morgen" in html.lower()
        assert "02.04.2026" in html
        assert "10:00" in html

    def test_owner_reminder_txt_renders(self):
        inspection = InspectionFactory(status="scheduled")
        txt = render_to_string(
            "emails/owner_reminder.txt",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "scheduled_date": "02.04.2026",
                "scheduled_time": "10:00",
            },
        )
        assert inspection.apartment.address in txt

    def test_inspector_reminder_html_renders(self):
        inspection = InspectionFactory(status="scheduled")
        html = render_to_string(
            "emails/inspector_reminder.html",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "scheduled_date": "02.04.2026",
                "scheduled_time": "10:00",
            },
        )
        assert inspection.apartment.address in html

    def test_inspector_reminder_txt_renders(self):
        inspection = InspectionFactory(status="scheduled")
        txt = render_to_string(
            "emails/inspector_reminder.txt",
            {
                "inspection": inspection,
                "apartment": inspection.apartment,
                "scheduled_date": "02.04.2026",
                "scheduled_time": "10:00",
            },
        )
        assert inspection.apartment.address in txt
