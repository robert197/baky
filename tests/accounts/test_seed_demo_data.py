"""Tests for the seed_demo_data management command."""

import pytest
from django.core.management import call_command

from apps.accounts.models import OnboardingProgress, Subscription, User
from apps.apartments.models import Apartment
from apps.inspections.models import Inspection, InspectionItem, Photo
from apps.reports.models import Report


def _seed(**kwargs):
    """Call seed_demo_data with --force (pytest-django sets DEBUG=False)."""
    call_command("seed_demo_data", force=True, **kwargs)


@pytest.mark.django_db
class TestSeedDemoDataUsers:
    def test_creates_demo_users(self):
        _seed()
        assert User.objects.filter(email="anna@example.at", role="owner").exists()
        assert User.objects.filter(email="markus@example.at", role="owner").exists()
        assert User.objects.filter(email="sophie@example.at", role="owner").exists()
        assert User.objects.filter(email="lisa@baky.at", role="inspector").exists()
        assert User.objects.filter(email="tom@baky.at", role="inspector").exists()
        assert User.objects.filter(email="admin@baky.at", role="admin").exists()

    def test_users_have_full_names(self):
        _seed()
        anna = User.objects.get(email="anna@example.at")
        assert anna.first_name == "Anna"
        assert anna.last_name == "Müller"

    def test_users_can_login(self):
        _seed()
        anna = User.objects.get(email="anna@example.at")
        assert anna.check_password("demo1234")
        admin = User.objects.get(email="admin@baky.at")
        assert admin.check_password("admin1234")

    def test_creates_subscriptions_for_owners(self):
        _seed()
        anna = User.objects.get(email="anna@example.at")
        assert anna.subscription.plan == Subscription.Plan.BASIS
        assert anna.subscription.status == Subscription.Status.ACTIVE
        markus = User.objects.get(email="markus@example.at")
        assert markus.subscription.plan == Subscription.Plan.PREMIUM
        sophie = User.objects.get(email="sophie@example.at")
        assert sophie.subscription.plan == Subscription.Plan.STANDARD

    def test_creates_onboarding_progress(self):
        _seed()
        for email in ["anna@example.at", "markus@example.at", "sophie@example.at"]:
            user = User.objects.get(email=email)
            assert user.onboarding.is_complete is True

    def test_idempotent_users(self):
        _seed()
        _seed()
        assert User.objects.filter(email="anna@example.at").count() == 1
        assert Subscription.objects.filter(owner__email="anna@example.at").count() == 1
        assert OnboardingProgress.objects.filter(user__email="anna@example.at").count() == 1


@pytest.mark.django_db
class TestSeedDemoDataApartments:
    def test_creates_five_apartments(self):
        _seed()
        assert Apartment.objects.count() == 5

    def test_anna_has_two_apartments(self):
        _seed()
        anna = User.objects.get(email="anna@example.at")
        assert anna.apartments.count() == 2

    def test_markus_has_three_apartments(self):
        _seed()
        markus = User.objects.get(email="markus@example.at")
        assert markus.apartments.count() == 3

    def test_apartments_have_checklist_templates(self):
        _seed()
        for apt in Apartment.objects.all():
            assert apt.checklist_template is not None
            assert apt.checklist_template.items

    def test_various_access_methods(self):
        _seed()
        methods = set(Apartment.objects.values_list("access_method", flat=True))
        assert len(methods) >= 2

    def test_paused_apartment_exists(self):
        _seed()
        assert Apartment.objects.filter(status="paused").exists()

    def test_idempotent_apartments(self):
        _seed()
        _seed()
        assert Apartment.objects.count() == 5


@pytest.mark.django_db
class TestSeedDemoDataInspections:
    def test_creates_fifteen_inspections(self):
        _seed()
        assert Inspection.objects.count() == 15

    def test_completed_inspections(self):
        _seed()
        assert Inspection.objects.filter(status="completed").count() == 10

    def test_scheduled_inspections(self):
        _seed()
        assert Inspection.objects.filter(status="scheduled").count() == 4

    def test_in_progress_inspection(self):
        _seed()
        assert Inspection.objects.filter(status="in_progress").count() == 1

    def test_completed_have_rating(self):
        _seed()
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.overall_rating in ["ok", "attention", "urgent"]

    def test_completed_have_timestamps(self):
        _seed()
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.started_at is not None
            assert insp.completed_at is not None

    def test_inspections_have_time_slot(self):
        _seed()
        for insp in Inspection.objects.all():
            assert insp.time_slot in ["morning", "midday", "afternoon"]

    def test_inspections_have_scheduled_end(self):
        _seed()
        for insp in Inspection.objects.all():
            assert insp.scheduled_end is not None

    def test_inspections_within_business_hours(self):
        _seed()
        from django.utils import timezone

        for insp in Inspection.objects.all():
            local = timezone.localtime(insp.scheduled_at)
            assert 8 <= local.hour < 16

    def test_idempotent_inspections(self):
        _seed()
        _seed()
        assert Inspection.objects.count() == 15


@pytest.mark.django_db
class TestSeedDemoDataResults:
    def test_completed_inspections_have_items(self):
        _seed()
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.items.count() > 0

    def test_flagged_items_exist(self):
        _seed()
        assert InspectionItem.objects.filter(result="flagged").count() > 0

    def test_flagged_items_have_severity(self):
        _seed()
        for item in InspectionItem.objects.filter(result="flagged"):
            assert item.severity != "none"

    def test_completed_inspections_have_reports(self):
        _seed()
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.report is not None
            assert insp.report.status == "completed"
            assert insp.report.html_content

    def test_flagged_items_have_photos(self):
        _seed()
        flagged_with_photos = InspectionItem.objects.filter(result="flagged", photos__isnull=False).distinct()
        assert flagged_with_photos.exists()

    def test_idempotent_items_and_reports(self):
        _seed()
        items_count = InspectionItem.objects.count()
        photos_count = Photo.objects.count()
        reports_count = Report.objects.count()
        _seed()
        assert InspectionItem.objects.count() == items_count
        assert Photo.objects.count() == photos_count
        assert Report.objects.count() == reports_count


@pytest.mark.django_db
class TestSeedAll:
    def test_seed_all_delegates_to_seed_demo_data(self):
        call_command("seed_all", force=True)
        assert User.objects.filter(email="anna@example.at").exists()
        assert Apartment.objects.count() == 5
        assert Inspection.objects.count() == 15


@pytest.mark.django_db
class TestSeedDemoDataGuards:
    def test_refuses_when_debug_false(self):
        """pytest-django already sets DEBUG=False, so no override needed."""
        from io import StringIO

        out = StringIO()
        call_command("seed_demo_data", stdout=out)
        output = out.getvalue().lower()
        assert "production" in output or "debug" in output
        assert User.objects.filter(email="anna@example.at").count() == 0

    def test_force_flag_overrides_guard(self):
        """--force should work even with DEBUG=False."""
        call_command("seed_demo_data", force=True)
        assert User.objects.filter(email="anna@example.at").exists()
