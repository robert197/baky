---
title: "Django partial unique index + IntegrityError handling pattern"
module: inspections, dashboard
severity: high
tags: [django, postgresql, race-condition, transaction, unique-constraint]
date: 2026-04-02
issue: "#82"
---

# Django Partial Unique Index + IntegrityError Handling

## Problem

When enforcing business uniqueness constraints (e.g., one booking per time slot per day),
application-level validation in `Model.clean()` has a TOCTOU race condition:

1. Request A: `clean()` checks — no conflict → passes
2. Request B: `clean()` checks — no conflict → passes
3. Request A: `save()` → succeeds
4. Request B: `save()` → **should fail but doesn't** (without DB constraint)

## Root Cause

Django's `clean()` method performs a SELECT query to check for conflicts, then `save()` does
the INSERT. Under `READ COMMITTED` isolation (PostgreSQL default), both transactions see the
same snapshot and both pass the check.

## Solution: Layered Defense

### Layer 1: Application-level check in `clean()` (user-friendly errors)

```python
if self.time_slot:
    global_conflict = Inspection.objects.filter(
        scheduled_at__date=local_date,
        time_slot=self.time_slot,
        status__in=[...active statuses...],
    )
    if self.pk:
        global_conflict = global_conflict.exclude(pk=self.pk)
    if global_conflict.exists():
        errors["time_slot"] = "Dieser Termin ist bereits vergeben."
```

### Layer 2: Database partial unique index (safety net)

```sql
CREATE UNIQUE INDEX unique_active_slot_per_day
ON inspections_inspection (
    DATE(scheduled_at AT TIME ZONE 'Europe/Vienna'),
    time_slot
)
WHERE status IN ('scheduled', 'in_progress', 'completed')
AND time_slot != '';
```

### Layer 3: Catch IntegrityError in the view (graceful degradation)

```python
from django.db import IntegrityError, transaction

try:
    with transaction.atomic():
        obj = Model(...)
        obj.full_clean()
        obj.save()
except ValidationError as e:
    # Normal validation failure — show user-friendly message
    ...
except IntegrityError:
    # Race condition caught by DB — show same friendly message
    return render(request, "error.html", {"error": "Slot already taken."})
```

## Prevention

When adding a uniqueness constraint enforced via `clean()`:

1. **Always add a database-level constraint** (unique index, partial unique index, or CHECK constraint)
2. **Always catch IntegrityError** in the view alongside ValidationError
3. **Always wrap in `transaction.atomic()`** to ensure clean rollback
4. **Document timezone coupling** if the DB constraint uses timezone-aware expressions

## Key Gotcha

`transaction.atomic()` alone does NOT prevent the race. It only ensures rollback on failure.
The DB unique index is what actually prevents duplicate inserts. The `IntegrityError` catch
ensures the user sees a friendly message instead of a 500 error.
