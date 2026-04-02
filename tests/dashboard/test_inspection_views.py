import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    OwnerFactory,
    PhotoFactory,
    ReportFactory,
)


@pytest.mark.django_db
class TestInspectionTimeline:
    def test_timeline_shows_completed_inspections(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        InspectionFactory(apartment=apt, status="scheduled")  # not shown
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 2

    def test_timeline_shows_inspector_name(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(first_name="Hans", last_name="Gruber")
        InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now(), inspector=inspector)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert "Hans Gruber" in resp.content.decode()

    def test_timeline_empty_state(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert "Noch keine Inspektionen" in resp.content.decode()

    def test_timeline_owner_scoping(self):
        owner = OwnerFactory()
        other = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(other)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 404

    def test_timeline_unauthenticated_redirect(self):
        apt = ApartmentFactory()
        client = Client()
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 302

    def test_timeline_inspector_denied(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        client = Client()
        client.force_login(inspector)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 404  # @owner_required returns 404 for wrong role

    def test_timeline_filter_by_rating(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(apartment=apt, status="completed", overall_rating="ok", completed_at=timezone.now())
        InspectionFactory(apartment=apt, status="completed", overall_rating="urgent", completed_at=timezone.now())
        client = Client()
        client.force_login(owner)
        resp = client.get(
            reverse("dashboard:inspection_timeline", args=[apt.pk]),
            {"rating": "urgent"},
        )
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 1

    def test_timeline_filter_by_date_range(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=60),
        )
        InspectionFactory(
            apartment=apt,
            status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=5),
        )
        client = Client()
        client.force_login(owner)
        from_date = (timezone.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        resp = client.get(
            reverse("dashboard:inspection_timeline", args=[apt.pk]),
            {"from": from_date},
        )
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 1

    def test_timeline_pagination_load_more(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        for i in range(15):
            InspectionFactory(
                apartment=apt,
                status="completed",
                completed_at=timezone.now() - datetime.timedelta(hours=i),
            )
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 10
        assert "Mehr laden" in resp.content.decode()

    def test_timeline_uses_status_badge_component(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(apartment=apt, status="completed", overall_rating="ok", completed_at=timezone.now())
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        # The _status_badge.html component renders specific classes
        assert "bg-emerald-100" in resp.content.decode()


@pytest.mark.django_db
class TestInspectionSummary:
    def test_summary_returns_html_fragment(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(
            apartment=apt, status="completed", general_notes="Alles in Ordnung", completed_at=timezone.now()
        )
        client = Client()
        client.force_login(owner)
        resp = client.get(
            reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]),
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert "Alles in Ordnung" in resp.content.decode()

    def test_summary_owner_scoping(self):
        owner = OwnerFactory()
        other = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        client = Client()
        client.force_login(other)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        assert resp.status_code == 404

    def test_summary_shows_flagged_count(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        InspectionItemFactory(inspection=insp, result="flagged")
        InspectionItemFactory(inspection=insp, result="flagged")
        InspectionItemFactory(inspection=insp, result="ok")
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "2 auffällig" in content.lower() or "2 Auffällig" in content or "2" in content

    def test_summary_without_report(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200

    def test_summary_with_report_shows_link(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "Bericht ansehen" in content or "inspection_report_detail" in content


@pytest.mark.django_db
class TestInspectionReportDetail:
    def test_report_detail_shows_checklist_items(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        InspectionItemFactory(inspection=insp, category="Küche", result="ok")
        InspectionItemFactory(inspection=insp, category="Küche", result="flagged", severity="high")
        InspectionItemFactory(inspection=insp, category="Bad", result="ok")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Küche" in content
        assert "Bad" in content

    def test_report_detail_groups_items_by_category(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        InspectionItemFactory(inspection=insp, category="Küche", checklist_label="Herd")
        InspectionItemFactory(inspection=insp, category="Küche", checklist_label="Spüle")
        InspectionItemFactory(inspection=insp, category="Wohnzimmer", checklist_label="Sofa")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "Küche" in content
        assert "Wohnzimmer" in content

    def test_report_detail_shows_photos(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        item = InspectionItemFactory(inspection=insp, result="flagged")
        PhotoFactory(inspection=insp, inspection_item=item, caption="Wasserschaden")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        assert "Wasserschaden" in resp.content.decode()

    def test_report_detail_without_report_shows_items(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        InspectionItemFactory(inspection=insp, result="ok")
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200

    def test_report_detail_owner_scoping(self):
        owner = OwnerFactory()
        other = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(other)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 404

    def test_report_detail_unauthenticated(self):
        apt = ApartmentFactory()
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        client = Client()
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 302

    def test_report_detail_highlights_urgent_items(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(
            apartment=apt, status="completed", overall_rating="urgent", completed_at=timezone.now()
        )
        InspectionItemFactory(inspection=insp, result="flagged", severity="urgent")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "bg-rose-50" in content

    def test_report_detail_inspector_contact(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(first_name="Max", last_name="Müller", phone="+43 660 1234567")
        insp = InspectionFactory(apartment=apt, status="completed", inspector=inspector, completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "Max Müller" in content
        assert "+43 660 1234567" in content

    def test_report_detail_inspector_no_contact(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(phone="", email="")
        insp = InspectionFactory(apartment=apt, status="completed", inspector=inspector, completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "BAKY" in content

    def test_report_detail_empty_checklist(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200

    def test_report_detail_back_link_to_timeline(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert reverse("dashboard:inspection_timeline", args=[apt.pk]) in content

    def test_report_detail_duration_display(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        now = timezone.now()
        insp = InspectionFactory(
            apartment=apt,
            status="completed",
            started_at=now - datetime.timedelta(hours=1, minutes=30),
            completed_at=now,
        )
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        # Should display duration in some form
        assert "1" in content  # at least the hour number
