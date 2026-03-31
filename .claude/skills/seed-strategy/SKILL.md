---
name: seed-strategy
description: Reference for BAKY's seed data strategy. Seed data grows incrementally as features are built, enabling e2e validation at every stage.
user-invokable: true
---

# BAKY Seed Data Strategy

## Principle: Seeds Grow With Features

Seed data is NOT a one-time dump at the end. Each feature adds the seeds it needs,
and ALL previous seeds remain valid. This ensures e2e tests work at every stage.

## Seed Layers

Seeds are organized in layers that build on each other:

### Layer 0: Users & Auth (added with #8)
```python
SEED_USERS = {
    "admin": {"email": "admin@baky.at", "password": "admin1234", "role": "admin"},
    "owner_anna": {"email": "anna@example.at", "password": "demo1234", "role": "owner", "name": "Anna Müller"},
    "owner_markus": {"email": "markus@example.at", "password": "demo1234", "role": "owner", "name": "Markus Weber"},
    "inspector_lisa": {"email": "lisa@baky.at", "password": "demo1234", "role": "inspector", "name": "Lisa Berger"},
}
```

### Layer 1: Apartments (added with #7)
```python
SEED_APARTMENTS = [
    {"owner": "owner_anna", "address": "Mariahilfer Straße 45/12, 1060 Wien", "access": "lockbox", "access_code": "4521", "status": "active"},
    {"owner": "owner_anna", "address": "Praterstraße 78/3, 1020 Wien", "access": "smart_lock", "access_code": "APP-CODE-789", "status": "active"},
    {"owner": "owner_markus", "address": "Kärntner Ring 15/8, 1010 Wien", "access": "key_handover", "status": "active"},
    {"owner": "owner_markus", "address": "Wiedner Hauptstraße 90/5, 1050 Wien", "access": "lockbox", "access_code": "9012", "status": "active"},
    {"owner": "owner_markus", "address": "Landstraßer Hauptstraße 33/7, 1030 Wien", "access": "lockbox", "access_code": "3345", "status": "paused"},
]
```

### Layer 2: Checklists (added with #10, #30)
- Default checklist fixture loaded per apartment
- Customized versions for each apartment (some items toggled off)

### Layer 3: Inspections (added with #27)
```python
SEED_INSPECTIONS = [
    # Completed inspections (for report testing)
    {"apartment": 0, "inspector": "inspector_lisa", "status": "completed", "rating": "ok", "days_ago": 14},
    {"apartment": 0, "inspector": "inspector_lisa", "status": "completed", "rating": "attention", "days_ago": 7},
    {"apartment": 1, "inspector": "inspector_lisa", "status": "completed", "rating": "ok", "days_ago": 10},
    {"apartment": 2, "inspector": "inspector_lisa", "status": "completed", "rating": "urgent", "days_ago": 3},
    # Scheduled inspections (for inspector app testing)
    {"apartment": 0, "inspector": "inspector_lisa", "status": "scheduled", "days_from_now": 0},  # Today!
    {"apartment": 3, "inspector": "inspector_lisa", "status": "scheduled", "days_from_now": 1},
    {"apartment": 1, "inspector": "inspector_lisa", "status": "scheduled", "days_from_now": 3},
]
```

### Layer 4: Inspection Results (added with #20, #22)
- InspectionItems for completed inspections (mix of OK/Flag/N.A.)
- Photos (placeholder images) for flagged items
- General notes

### Layer 5: Reports (added with #23)
- Generated reports for completed inspections

### Layer 6: Subscriptions (added with #18)
- Anna: Basis plan, active
- Markus: Extra plan, active

## Master Seed Command

```bash
make seed
# Runs: python manage.py seed_all
```

`seed_all` calls each layer's seed command in order. Each is idempotent (safe to re-run).

```python
# management/commands/seed_all.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        call_command("seed_users")
        call_command("seed_apartments")
        call_command("loaddata", "default_checklist")
        call_command("seed_inspections")
        call_command("seed_inspection_results")
        call_command("seed_reports")
        call_command("seed_subscriptions")
        self.stdout.write(self.style.SUCCESS("All seed data loaded."))
```

Each command checks if data exists before creating (idempotent):
```python
user, created = User.objects.get_or_create(email=email, defaults={...})
```

## E2E Tests Use Seeds

E2E tests assume seed data exists:

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session", autouse=True)
def seed_data(live_server):
    call_command("seed_all")
```

## When Adding a New Feature

1. Does the feature need new seed data? → Add a new seed command
2. Register it in `seed_all` (in the right order)
3. Existing seeds and e2e tests still work (additive only, never destructive)
