---
title: "feat: Enforce global slot exclusivity (one booking per time slot per day)"
type: feat
status: active
date: 2026-04-02
issue: "#82"
---

# Enforce Global Slot Exclusivity

## Overview

Currently, slot availability is checked per-apartment only — multiple owners can book the same time slot (e.g., Monday Morning) for different apartments. Since BAKY operates with limited inspectors, each slot (Morning/Midday/Afternoon) should only be available to one booking globally.

**Goal**: One `Inspection` per `(date, time_slot)` combination across ALL apartments.

## Key Decisions

1. **Keep same-apartment-same-day check**: Both rules coexist — one apartment per day AND one booking per slot globally.
2. **Database-level protection**: Add a partial unique index via raw SQL migration on `(date(scheduled_at), time_slot)` for non-cancelled inspections.
3. **Transaction safety**: Wrap `book_slot()` in `transaction.atomic()` to prevent race conditions (follows pattern in `submit_inspection()`).
4. **Empty `time_slot` handling**: Global check only applies when `time_slot` is set. Admin-created inspections without `time_slot` are unaffected.
5. **Owner cancellation**: Out of scope (issue #83).
6. **Calendar UX improvements**: Out of scope (issue #84).

## Acceptance Criteria

- [ ] Owner A books Monday Morning → Monday Morning shows unavailable for Owner B
- [ ] Cancelled bookings free up the slot
- [ ] Same owner can still book different slots on same day for different apartments
- [ ] Error message: "Dieser Termin ist bereits vergeben."
- [ ] Availability correctly updates after booking
- [ ] DB-level constraint prevents race-condition double-bookings

## Files to Modify

| File | Change |
|------|--------|
| `apps/inspections/models.py` | Add global slot check in `clean()` |
| `apps/inspections/migrations/NNNN_*.py` | Partial unique index migration |
| `apps/dashboard/views.py` | Update `_get_week_availability()` to global, wrap `book_slot()` in `transaction.atomic()` |
| `tests/inspections/test_scheduling.py` | New `TestGlobalSlotExclusivity` class |
| `tests/dashboard/test_booking_views.py` | Update conflicting tests, add global slot view tests |

## Implementation Tasks

### Task 1: Add global slot validation to `Inspection.clean()`

**Test first** (`tests/inspections/test_scheduling.py`):

```python
@pytest.mark.django_db
class TestGlobalSlotExclusivity:
    def test_same_slot_different_apartment_rejected(self):
        """Two apartments on the same date+slot should be rejected."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
        )

        inspection2 = Inspection(
            apartment=apt2,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
            status=Inspection.Status.SCHEDULED,
        )
        with pytest.raises(ValidationError) as exc_info:
            inspection2.full_clean()
        assert "bereits vergeben" in str(exc_info.value)

    def test_different_slot_same_day_accepted(self):
        """Different slots on the same day should be fine."""
        owner1 = OwnerFactory()
        owner2 = OwnerFactory()
        SubscriptionFactory(owner=owner1, plan="standard")
        SubscriptionFactory(owner=owner2, plan="standard")
        apt1 = ApartmentFactory(owner=owner1)
        apt2 = ApartmentFactory(owner=owner2)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
        )

        inspection2 = Inspection(
            apartment=apt2,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 13, 30, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 16, 0, tzinfo=VIENNA_TZ),
            time_slot="afternoon",
            status=Inspection.Status.SCHEDULED,
        )
        inspection2.full_clean()  # Should not raise

    def test_cancelled_slot_can_be_rebooked(self):
        """Cancelled inspection should free the slot."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
            status=Inspection.Status.CANCELLED,
        )

        inspection2 = Inspection(
            apartment=apt2,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
            status=Inspection.Status.SCHEDULED,
        )
        inspection2.full_clean()  # Should not raise

    def test_empty_timeslot_skips_global_check(self):
        """Admin-created inspections without time_slot bypass global check."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        InspectionFactory(
            apartment=apt1,
            inspector=inspector,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
        )

        # Admin inspection with no time_slot — same time but no slot enforcement
        inspection2 = Inspection(
            apartment=apt2,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="",  # No time_slot
            status=Inspection.Status.SCHEDULED,
        )
        inspection2.full_clean()  # Should not raise

    def test_updating_existing_inspection_passes(self):
        """Editing an existing inspection should not conflict with itself."""
        owner = OwnerFactory()
        SubscriptionFactory(owner=owner, plan="standard")
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory()
        target_date = _future_date(days_ahead=5)

        inspection = InspectionFactory(
            apartment=apt,
            inspector=inspector,
            scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
            scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
            time_slot="morning",
        )
        inspection.general_notes = "Updated"
        inspection.full_clean()  # Should not raise (exclude self.pk)
```

**Implementation** (`apps/inspections/models.py:112`): Add a global slot check BEFORE the existing same-apartment-same-day check:

```python
# Validate global slot exclusivity (one booking per date+time_slot)
if self.time_slot:
    local_date = timezone.localtime(self.scheduled_at).date()
    global_conflict = Inspection.objects.filter(
        scheduled_at__date=local_date,
        time_slot=self.time_slot,
        status__in=[self.Status.SCHEDULED, self.Status.IN_PROGRESS, self.Status.COMPLETED],
    )
    if self.pk:
        global_conflict = global_conflict.exclude(pk=self.pk)
    if global_conflict.exists():
        errors["time_slot"] = "Dieser Termin ist bereits vergeben."
```

**Verify**: `make test ARGS="-k TestGlobalSlotExclusivity"`

### Task 2: Add database-level partial unique index

**Create migration** (`apps/inspections/migrations/NNNN_add_global_slot_unique_constraint.py`):

```python
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inspections", "<previous_migration>"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX unique_active_slot_per_day
                ON inspections_inspection (DATE(scheduled_at AT TIME ZONE 'Europe/Vienna'), time_slot)
                WHERE status IN ('scheduled', 'in_progress', 'completed')
                AND time_slot != '';
            """,
            reverse_sql="DROP INDEX IF EXISTS unique_active_slot_per_day;",
        ),
    ]
```

**Test**: `make migrate` succeeds, then `make test` — all existing tests still pass.

### Task 3: Update `_get_week_availability()` for global slot checking

**Test first** (`tests/dashboard/test_booking_views.py`) — add to existing `TestBookingCalendarView`:

```python
def test_availability_shows_globally_booked_slots(self):
    """Slot booked by another owner should show as unavailable."""
    owner1 = OwnerFactory()
    owner2 = OwnerFactory()
    SubscriptionFactory(owner=owner1, plan="standard")
    SubscriptionFactory(owner=owner2, plan="standard")
    apt1 = ApartmentFactory(owner=owner1)
    apt2 = ApartmentFactory(owner=owner2)
    inspector = InspectorFactory()
    target_date = _future_date(days_ahead=5)

    # Owner1 books morning slot
    InspectionFactory(
        apartment=apt1,
        inspector=inspector,
        scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
        scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
        time_slot="morning",
    )

    # Owner2 views calendar — morning should be unavailable
    client = Client()
    client.force_login(owner2)
    week_offset = ...  # calculate offset for target_date
    resp = client.get(
        reverse("dashboard:booking_calendar"),
        {"apartment": apt2.pk, "week": week_offset},
    )
    assert resp.status_code == 200
    # Morning slot should not be available
```

**Implementation** (`apps/dashboard/views.py:407-455`):

Change `_get_week_availability()` to:
1. Query globally booked `(date, time_slot)` pairs instead of per-apartment dates
2. Check per-slot availability instead of per-day

```python
def _get_week_availability(start_date, apartment, owner):
    subscription = _get_subscription_or_none(owner)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        return {"days": [], "used": 0, "limit": 0, "limit_reached": True}

    used = subscription.get_inspections_used_this_month()
    limit = subscription.get_monthly_inspection_limit()
    limit_reached = used >= limit

    now = timezone.now()
    week_dates = [start_date + timedelta(days=i) for i in range(7)]

    # Global query: find all booked (date, time_slot) pairs across ALL apartments
    booked_slots = set(
        Inspection.objects.filter(
            scheduled_at__date__in=week_dates,
            time_slot__in=[ts.value for ts in Inspection.TimeSlot],
            status__in=[Inspection.Status.SCHEDULED, Inspection.Status.IN_PROGRESS, Inspection.Status.COMPLETED],
        ).values_list("scheduled_at__date", "time_slot")
    )

    # Also check same-apartment-same-day (existing rule)
    apartment_booked_dates = set(
        Inspection.objects.filter(
            apartment=apartment,
            scheduled_at__date__in=week_dates,
            status__in=[Inspection.Status.SCHEDULED, Inspection.Status.IN_PROGRESS, Inspection.Status.COMPLETED],
        ).values_list("scheduled_at__date", flat=True).distinct()
    )

    days = []
    for current_date in week_dates:
        day_slots = []
        has_apartment_booking = current_date in apartment_booked_dates

        for slot_key in Inspection.TimeSlot:
            sh, sm, eh, em = Inspection.SLOT_TIMES[slot_key]
            slot_start = datetime(current_date.year, current_date.month, current_date.day, sh, sm, tzinfo=VIENNA_TZ)
            is_past = now >= slot_start - timedelta(hours=24)
            is_globally_booked = (current_date, slot_key.value) in booked_slots

            day_slots.append({
                "key": slot_key.value,
                "label": slot_key.label,
                "start": f"{sh:02d}:{sm:02d}",
                "end": f"{eh:02d}:{em:02d}",
                "available": not is_past and not is_globally_booked and not has_apartment_booking and not limit_reached,
                "is_past": is_past,
                "has_booking": is_globally_booked or has_apartment_booking,
            })
        days.append({"date": current_date, "slots": day_slots})

    return {"days": days, "used": used, "limit": limit, "limit_reached": limit_reached}
```

**Verify**: `make test ARGS="-k TestBookingCalendarView"`

### Task 4: Wrap `book_slot()` in `transaction.atomic()`

**Test** (`tests/dashboard/test_booking_views.py`):

```python
def test_global_slot_conflict_returns_error(self):
    """Booking a globally taken slot returns the correct error message."""
    owner1 = OwnerFactory()
    owner2 = OwnerFactory()
    SubscriptionFactory(owner=owner1, plan="standard")
    SubscriptionFactory(owner=owner2, plan="standard")
    apt1 = ApartmentFactory(owner=owner1)
    apt2 = ApartmentFactory(owner=owner2)
    inspector = InspectorFactory()
    target_date = _future_date(days_ahead=5)

    InspectionFactory(
        apartment=apt1,
        inspector=inspector,
        scheduled_at=datetime.datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=VIENNA_TZ),
        scheduled_end=datetime.datetime(target_date.year, target_date.month, target_date.day, 10, 30, tzinfo=VIENNA_TZ),
        time_slot="morning",
    )

    client = Client()
    client.force_login(owner2)
    resp = client.post(
        reverse("dashboard:book_slot"),
        {"apartment": apt2.pk, "date": target_date.isoformat(), "slot": "morning"},
    )
    assert resp.status_code == 200
    assert "bereits vergeben" in resp.content.decode()
    assert Inspection.objects.filter(apartment=apt2).count() == 0
```

**Implementation** (`apps/dashboard/views.py:517-589`):

Wrap the inspection creation in `transaction.atomic()`:

```python
from django.db import transaction

@owner_required
def book_slot(request):
    # ... existing validation ...

    with transaction.atomic():
        inspection = Inspection(
            apartment=apartment,
            inspector=None,
            scheduled_at=scheduled_at,
            scheduled_end=scheduled_end,
            time_slot=slot_key,
            status=Inspection.Status.SCHEDULED,
        )
        try:
            inspection.full_clean()
            inspection.save()
        except ValidationError as e:
            error_msg = ". ".join(msg for msgs in e.message_dict.values() for msg in msgs)
            return render(request, "dashboard/_booking_error.html", {"error": error_msg})

    # Notify admin (outside transaction)
    # ...
```

**Verify**: `make test ARGS="-k TestBookSlotView"`

### Task 5: Update conflicting tests

Two existing tests assert the OLD behavior (different apartments, same slot, same day = accepted). These must change:

1. **`tests/dashboard/test_booking_views.py:336` — `TestBookSlotView.test_different_apartment_same_day_accepted`**:
   - Rename to `test_different_apartment_same_slot_rejected`
   - Assert error response with "bereits vergeben"
   - Add new test: `test_different_apartment_different_slot_accepted` (apt1 morning, apt2 afternoon = OK)

2. **`tests/dashboard/test_booking_views.py:520` — `TestSameDayDuplicateValidation.test_different_apartment_same_day_accepted`**:
   - Rename to `test_different_apartment_same_slot_rejected`
   - Assert `ValidationError` with "bereits vergeben"
   - Add new test: `test_different_apartment_different_slot_accepted`

**Verify**: `make test` — full suite passes.

### Task 6: Run full validation

```bash
make lint
make test
make manage CMD="check"
```

All must pass before PR.

## System-Wide Impact

- **Interaction graph**: `book_slot()` → `Inspection.full_clean()` → `clean()` (new global check) → `save()`. Admin form also calls `full_clean()`, so admin-created inspections with `time_slot` set will also be subject to global exclusivity.
- **Error propagation**: `ValidationError` from `clean()` is caught in `book_slot()` and rendered as `_booking_error.html`. DB `IntegrityError` from the partial unique index is a safety net — should never be hit if application check works correctly.
- **State lifecycle**: `transaction.atomic()` ensures no partial state. If `full_clean()` fails, nothing is persisted.
- **API surface parity**: The admin `InspectionAdminForm` also calls `full_clean()`, so the constraint is enforced there too.

## Sources

- Issue: #82
- Calendar booking implementation: #66
- Key files: `apps/inspections/models.py:75-132`, `apps/dashboard/views.py:407-589`
- Pattern reference: `apps/inspections/views.py:386` (`submit_inspection` uses `transaction.atomic()`)
