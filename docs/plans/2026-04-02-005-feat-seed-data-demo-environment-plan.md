---
title: "feat: Seed data and demo environment"
type: feat
status: active
date: 2026-04-02
issue: 40
---

# Seed Data and Demo Environment

## Overview

Create a management command `seed_demo_data` that populates the database with realistic demo data for development, demos, and e2e testing. A thin `seed_all` wrapper calls it to match the existing Makefile target `make seed`.

## Problem Statement

Developers and the autopilot (Ralph Loop) need pre-populated data to test all features end-to-end. Without seed data, every manual test requires creating users, apartments, inspections, etc. from scratch.

## Proposed Solution

A single `seed_demo_data` command in `apps/accounts/management/commands/` that creates the full object graph in dependency order:

1. Users (3 owners + 2 inspectors + 1 admin)
2. Subscriptions (one per owner)
3. Apartments (5 total, auto-creates ChecklistTemplates via signal)
4. OnboardingProgress (completed for each owner)
5. Inspections (15 total: 10 completed, 1 in-progress, 4 scheduled)
6. InspectionItems (for completed + in-progress inspections)
7. Photos (placeholder images for flagged items)
8. Reports (for all completed inspections)

A `seed_all` command in the same directory simply calls `seed_demo_data`.

## Technical Considerations

### Inspection.clean() Bypass
Factory_boy's `DjangoModelFactory.create()` calls `save()` but NOT `full_clean()`. The seed command follows the same pattern — using `Inspection.objects.create()` directly. However, the data is constructed to be structurally valid:
- All scheduled_at within business hours (08:00-16:00 Vienna time)
- No inspector double-booking (different days per inspector)
- No same-apartment same-day (each apartment inspected on unique days)
- `scheduled_end` and `time_slot` always set

### Subscription Limits
Anna (Basis=2/month), Markus (Premium=8/month), Sophie (Standard=4/month, 0 apartments). Inspections spread across multiple months so limits aren't exceeded per month per owner.

### Idempotency
- Users: `get_or_create` by `email`
- Subscriptions: `get_or_create` by `owner` (OneToOne enforces uniqueness)
- Apartments: `get_or_create` by `address` + `owner`
- ChecklistTemplates: auto-created by Apartment post_save signal; signal checks `created` flag
- OnboardingProgress: `get_or_create` by `user`
- Inspections: `get_or_create` by `apartment` + `scheduled_at`
- InspectionItems: skipped if inspection already has items
- Photos: skipped if inspection already has photos
- Reports: `get_or_create` by `inspection` (OneToOne)

### Scheduled Inspections Stay Fresh
Future-dated inspections use `timezone.now() + timedelta(days=N)`. On re-run, `update_or_create` updates the `scheduled_at` to keep them in the future.

### Photo Handling
Uses `ContentFile` with a minimal valid JPEG blob (generated via Pillow) rather than `factory.django.ImageField`. This avoids factory_boy dependency in production code while still producing real images that pass `validate_photo_file` and trigger `create_thumbnail()`.

### Production Guard
Command refuses to run if `settings.DEBUG is False` unless `--force` flag is passed.

## Demo Accounts

| Role | Email | Password | Name | Plan |
|------|-------|----------|------|------|
| Admin | admin@baky.at | admin1234 | Admin User | — |
| Owner | anna@example.at | demo1234 | Anna Muller | Basis (2/month) |
| Owner | markus@example.at | demo1234 | Markus Weber | Premium (8/month) |
| Owner | sophie@example.at | demo1234 | Sophie Fischer | Standard (4/month) |
| Inspector | lisa@baky.at | demo1234 | Lisa Berger | — |
| Inspector | tom@baky.at | demo1234 | Tom Schneider | — |

## Apartment Distribution

| # | Owner | Address | Access | Status |
|---|-------|---------|--------|--------|
| 0 | Anna | Mariahilfer Straße 45/12, 1060 Wien | lockbox (4521) | active |
| 1 | Anna | Praterstraße 78/3, 1020 Wien | smart_lock (APP-789) | active |
| 2 | Markus | Kärntner Ring 15/8, 1010 Wien | key_handover | active |
| 3 | Markus | Wiedner Hauptstraße 90/5, 1050 Wien | lockbox (9012) | active |
| 4 | Markus | Landstraßer Hauptstraße 33/7, 1030 Wien | lockbox (3345) | paused |

Sophie has 0 apartments (tests empty dashboard state).

## Inspection Distribution (15 total)

All times in Europe/Vienna. Inspections spread across different days and months.

### Completed (10)

| # | Apt | Inspector | Days Ago | Slot | Rating | Items |
|---|-----|-----------|----------|------|--------|-------|
| 1 | 0 | Lisa | 45 | morning | ok | All OK |
| 2 | 0 | Lisa | 30 | midday | attention | 2 flagged |
| 3 | 1 | Lisa | 40 | morning | ok | All OK |
| 4 | 1 | Tom | 25 | afternoon | ok | All OK |
| 5 | 2 | Lisa | 35 | morning | urgent | 3 flagged (1 high severity) |
| 6 | 2 | Tom | 20 | midday | ok | All OK |
| 7 | 3 | Tom | 38 | morning | ok | All OK |
| 8 | 3 | Lisa | 15 | afternoon | attention | 1 flagged |
| 9 | 4 | Tom | 50 | morning | ok | All OK |
| 10 | 0 | Tom | 10 | midday | ok | All OK |

### In-Progress (1)

| # | Apt | Inspector | When | Slot |
|---|-----|-----------|------|------|
| 11 | 2 | Lisa | today 08:00 | morning |

### Scheduled (4)

| # | Apt | Inspector | Days From Now | Slot |
|---|-----|-----------|---------------|------|
| 12 | 0 | Lisa | +1 | morning |
| 13 | 1 | Lisa | +2 | midday |
| 14 | 3 | Tom | +1 | afternoon |
| 15 | 2 | Tom | +3 | morning |

## Acceptance Criteria

- [ ] `python manage.py seed_demo_data` populates all models
- [ ] `python manage.py seed_all` delegates to `seed_demo_data`
- [ ] `make seed` works via Docker
- [ ] Idempotent: running twice produces no errors and no duplicates
- [ ] Demo accounts documented in command output
- [ ] Production guard: refuses if `DEBUG=False` without `--force`
- [ ] All completed inspections have Reports with html_content
- [ ] All owners have Subscriptions and completed OnboardingProgress
- [ ] Inspector schedule view shows upcoming inspections
- [ ] Owner dashboard shows apartments, timeline, reports
- [ ] Admin sees all data

## Implementation Tasks

### Task 1: Create `seed_demo_data` management command — user and subscription seeding

**Files:**
- `apps/accounts/management/commands/seed_demo_data.py` (new)

**Test:** `tests/accounts/test_seed_demo_data.py` (new)

```python
# tests/accounts/test_seed_demo_data.py
import pytest
from django.core.management import call_command
from apps.accounts.models import User, Subscription, OnboardingProgress


@pytest.mark.django_db
class TestSeedDemoDataUsers:
    def test_creates_demo_users(self):
        call_command("seed_demo_data")
        assert User.objects.filter(email="anna@example.at", role="owner").exists()
        assert User.objects.filter(email="markus@example.at", role="owner").exists()
        assert User.objects.filter(email="sophie@example.at", role="owner").exists()
        assert User.objects.filter(email="lisa@baky.at", role="inspector").exists()
        assert User.objects.filter(email="tom@baky.at", role="inspector").exists()
        assert User.objects.filter(email="admin@baky.at", role="admin").exists()

    def test_users_have_full_names(self):
        call_command("seed_demo_data")
        anna = User.objects.get(email="anna@example.at")
        assert anna.first_name == "Anna"
        assert anna.last_name == "Müller"

    def test_users_can_login(self):
        call_command("seed_demo_data")
        anna = User.objects.get(email="anna@example.at")
        assert anna.check_password("demo1234")

    def test_creates_subscriptions_for_owners(self):
        call_command("seed_demo_data")
        anna = User.objects.get(email="anna@example.at")
        assert anna.subscription.plan == Subscription.Plan.BASIS
        assert anna.subscription.status == Subscription.Status.ACTIVE

    def test_creates_onboarding_progress(self):
        call_command("seed_demo_data")
        anna = User.objects.get(email="anna@example.at")
        assert anna.onboarding.is_complete is True

    def test_idempotent_users(self):
        call_command("seed_demo_data")
        call_command("seed_demo_data")
        assert User.objects.filter(email="anna@example.at").count() == 1
        assert Subscription.objects.filter(owner__email="anna@example.at").count() == 1
```

**Implementation:** Create `seed_demo_data.py` with `Command` class. Add production guard (`--force` flag). Define SEED_USERS dict with all 6 users. In `handle()`, iterate users with `get_or_create` by email, set password, first_name, last_name. Create Subscriptions and OnboardingProgress with `get_or_create`.

**Verify:** `make test ARGS="-k test_seed_demo_data"`

### Task 2: Apartment seeding

**Files:**
- `apps/accounts/management/commands/seed_demo_data.py` (extend)
- `tests/accounts/test_seed_demo_data.py` (extend)

```python
# Add to tests/accounts/test_seed_demo_data.py
from apps.apartments.models import Apartment, ChecklistTemplate


@pytest.mark.django_db
class TestSeedDemoDataApartments:
    def test_creates_five_apartments(self):
        call_command("seed_demo_data")
        assert Apartment.objects.count() == 5

    def test_anna_has_two_apartments(self):
        call_command("seed_demo_data")
        anna = User.objects.get(email="anna@example.at")
        assert anna.apartments.count() == 2

    def test_markus_has_three_apartments(self):
        call_command("seed_demo_data")
        markus = User.objects.get(email="markus@example.at")
        assert markus.apartments.count() == 3

    def test_apartments_have_checklist_templates(self):
        call_command("seed_demo_data")
        for apt in Apartment.objects.all():
            assert hasattr(apt, "checklist_template")
            assert apt.checklist_template.items  # Non-empty

    def test_various_access_methods(self):
        call_command("seed_demo_data")
        methods = set(Apartment.objects.values_list("access_method", flat=True))
        assert len(methods) >= 2  # At least 2 different methods

    def test_paused_apartment_exists(self):
        call_command("seed_demo_data")
        assert Apartment.objects.filter(status="paused").exists()

    def test_idempotent_apartments(self):
        call_command("seed_demo_data")
        call_command("seed_demo_data")
        assert Apartment.objects.count() == 5
```

**Implementation:** Define SEED_APARTMENTS list. Use `get_or_create` by `owner` + `address`. Set street, zip_code, city, access_method, access_code, status. ChecklistTemplate auto-created by signal — no manual creation needed.

**Verify:** `make test ARGS="-k test_seed_demo_data"`

### Task 3: Inspection seeding (completed, in-progress, scheduled)

**Files:**
- `apps/accounts/management/commands/seed_demo_data.py` (extend)
- `tests/accounts/test_seed_demo_data.py` (extend)

```python
# Add to tests/accounts/test_seed_demo_data.py
from apps.inspections.models import Inspection


@pytest.mark.django_db
class TestSeedDemoDataInspections:
    def test_creates_fifteen_inspections(self):
        call_command("seed_demo_data")
        assert Inspection.objects.count() == 15

    def test_completed_inspections(self):
        call_command("seed_demo_data")
        assert Inspection.objects.filter(status="completed").count() == 10

    def test_scheduled_inspections(self):
        call_command("seed_demo_data")
        assert Inspection.objects.filter(status="scheduled").count() == 4

    def test_in_progress_inspection(self):
        call_command("seed_demo_data")
        assert Inspection.objects.filter(status="in_progress").count() == 1

    def test_completed_have_rating(self):
        call_command("seed_demo_data")
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.overall_rating in ["ok", "attention", "urgent"]

    def test_completed_have_timestamps(self):
        call_command("seed_demo_data")
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.started_at is not None
            assert insp.completed_at is not None

    def test_inspections_have_time_slot(self):
        call_command("seed_demo_data")
        for insp in Inspection.objects.all():
            assert insp.time_slot in ["morning", "midday", "afternoon"]

    def test_inspections_have_scheduled_end(self):
        call_command("seed_demo_data")
        for insp in Inspection.objects.all():
            assert insp.scheduled_end is not None

    def test_inspections_within_business_hours(self):
        call_command("seed_demo_data")
        from django.utils import timezone
        for insp in Inspection.objects.all():
            local = timezone.localtime(insp.scheduled_at)
            assert 8 <= local.hour < 16

    def test_idempotent_inspections(self):
        call_command("seed_demo_data")
        call_command("seed_demo_data")
        assert Inspection.objects.count() == 15
```

**Implementation:** Define SEED_INSPECTIONS list with apartment index, inspector key, status, days_ago/days_from_now, time_slot, rating. Create timezone-aware datetimes using `SLOT_TIMES` mapping. Use `get_or_create` by `apartment` + `scheduled_at`. For completed: set `started_at`, `completed_at`, `overall_rating`. For in-progress: set `started_at`. For scheduled (future): use `update_or_create` to keep dates fresh on re-run.

**Verify:** `make test ARGS="-k test_seed_demo_data"`

### Task 4: InspectionItems, Photos, and Reports

**Files:**
- `apps/accounts/management/commands/seed_demo_data.py` (extend)
- `tests/accounts/test_seed_demo_data.py` (extend)

```python
# Add to tests/accounts/test_seed_demo_data.py
from apps.inspections.models import InspectionItem, Photo
from apps.reports.models import Report


@pytest.mark.django_db
class TestSeedDemoDataResults:
    def test_completed_inspections_have_items(self):
        call_command("seed_demo_data")
        for insp in Inspection.objects.filter(status="completed"):
            assert insp.items.count() > 0

    def test_flagged_items_exist(self):
        call_command("seed_demo_data")
        assert InspectionItem.objects.filter(result="flagged").count() > 0

    def test_flagged_items_have_severity(self):
        call_command("seed_demo_data")
        for item in InspectionItem.objects.filter(result="flagged"):
            assert item.severity != "none"

    def test_completed_inspections_have_reports(self):
        call_command("seed_demo_data")
        for insp in Inspection.objects.filter(status="completed"):
            assert hasattr(insp, "report")
            assert insp.report.status == "completed"
            assert insp.report.html_content

    def test_flagged_items_have_photos(self):
        call_command("seed_demo_data")
        flagged_with_photos = InspectionItem.objects.filter(
            result="flagged", photos__isnull=False
        ).distinct()
        assert flagged_with_photos.exists()

    def test_idempotent_items_and_reports(self):
        call_command("seed_demo_data")
        items_count = InspectionItem.objects.count()
        photos_count = Photo.objects.count()
        reports_count = Report.objects.count()
        call_command("seed_demo_data")
        assert InspectionItem.objects.count() == items_count
        assert Photo.objects.count() == photos_count
        assert Report.objects.count() == reports_count
```

**Implementation:**
- **InspectionItems:** For each completed/in-progress inspection, read the apartment's checklist_template items. Create InspectionItem per checklist item. For "ok"-rated inspections: all items OK. For "attention": 1-2 items flagged with LOW/MEDIUM severity. For "urgent": 3+ items flagged with HIGH/URGENT severity. Skip if inspection already has items.
- **Photos:** Generate a minimal JPEG using Pillow (`Image.new("RGB", (100, 100), color)` + save to `BytesIO`). Create 1 photo per flagged item + 1 general photo per completed inspection. Skip if inspection already has photos.
- **Reports:** For each completed inspection, `get_or_create` Report with `status=COMPLETED`, `html_content` with a simple template, `generated_at` = inspection.completed_at + 1 hour.

**Verify:** `make test ARGS="-k test_seed_demo_data"`

### Task 5: `seed_all` wrapper and command output

**Files:**
- `apps/accounts/management/commands/seed_all.py` (new)
- `tests/accounts/test_seed_demo_data.py` (extend)

```python
# Add to tests/accounts/test_seed_demo_data.py
@pytest.mark.django_db
class TestSeedAll:
    def test_seed_all_delegates_to_seed_demo_data(self):
        call_command("seed_all")
        assert User.objects.filter(email="anna@example.at").exists()
        assert Apartment.objects.count() == 5
        assert Inspection.objects.count() == 15

    def test_seed_demo_data_output(self, capsys):
        call_command("seed_demo_data", stdout=capsys)
        # Command should print a summary
```

**Implementation:**
- `seed_all.py`: Simple command that calls `call_command("seed_demo_data")`.
- Add summary output to `seed_demo_data`: print counts of created/skipped objects and demo credentials table.

**Verify:** `make test ARGS="-k test_seed"` and `make seed`

### Task 6: Production guard and documentation

**Files:**
- `apps/accounts/management/commands/seed_demo_data.py` (extend)
- `tests/accounts/test_seed_demo_data.py` (extend)

```python
# Add to tests/accounts/test_seed_demo_data.py
from django.test import override_settings


@pytest.mark.django_db
class TestSeedDemoDataGuards:
    @override_settings(DEBUG=False)
    def test_refuses_in_production(self):
        from io import StringIO
        out = StringIO()
        call_command("seed_demo_data", stdout=out)
        assert "production" in out.getvalue().lower() or "debug" in out.getvalue().lower()
        assert User.objects.filter(email="anna@example.at").count() == 0

    @override_settings(DEBUG=False)
    def test_force_flag_overrides_guard(self):
        call_command("seed_demo_data", force=True)
        assert User.objects.filter(email="anna@example.at").exists()
```

**Implementation:**
- Add `--force` argument via `add_arguments`
- Check `settings.DEBUG` at start of `handle()`: if not DEBUG and not force, print warning and return
- Add demo credentials to command stdout output

**Verify:** `make test ARGS="-k test_seed_demo_data"` then `make lint`

## Sources

- Existing factories: `tests/factories.py`
- Seed strategy skill: `.claude/skills/seed-strategy/SKILL.md`
- Management command patterns: `apps/inspections/management/commands/cleanup_expired_photos.py`
- Apartment signal: `apps/apartments/signals.py`
- Inspection validation: `apps/inspections/models.py:75-132`
- Related issue: #40
