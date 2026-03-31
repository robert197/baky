---
title: "feat: Set up testing infrastructure with pytest-django"
type: feat
status: completed
date: 2026-03-31
issue: "#5"
---

# Set Up Testing Infrastructure

## Overview

Configure a complete pytest-django testing setup so that Claude Code and developers can verify implementations via `make test`. The infrastructure is partially scaffolded (deps installed, config exists, two factories written) but needs completion: add missing deps, fix conftest inconsistencies, create directory structure, add coverage config, and write a smoke test to prove it works.

## Current State

| Component | Status | Notes |
|-----------|--------|-------|
| pytest, pytest-django, pytest-cov, factory-boy | Installed | In `requirements/local.txt` |
| pytest-xdist | **Missing** | Listed in issue requirements but not installed |
| `pyproject.toml` pytest config | Exists | `--reuse-db`, `--tb=short`, correct settings module |
| `tests/conftest.py` | Exists | Manual fixtures (not using factories) |
| `tests/factories.py` | Exists | `UserFactory`, `InspectorFactory` |
| Test directory structure | Flat | No app-mirroring subdirectories |
| Actual test files | **None** | Zero `test_*.py` files |
| `make test` | Works | `docker compose exec web pytest $(ARGS)` |
| Coverage config | **Missing** | `--cov` not in addopts, no source/omit config |

## Decisions

1. **Factories for non-existent models**: Only create factories for models that exist now (`User`). `ApartmentFactory`, `InspectionFactory` etc. will be added when issue #7 (core models) lands. Creating factories for non-existent models would break test collection.

2. **pytest-xdist**: Add to `requirements/local.txt` but do NOT add `-n` to default `addopts`. Parallel execution is opt-in via `make test ARGS="-n auto"`.

3. **Coverage**: Do NOT add `--cov` to default `addopts` (slows TDD cycles). Add a separate `make coverage` Makefile target. Coverage report is available on demand, not forced on every run.

4. **conftest.py fixtures**: Replace manual `create_user()` fixtures with factory-based ones to establish a single canonical pattern.

5. **Base test classes**: Skip. No real test patterns exist yet to abstract over. Premature abstraction in test infra creates friction. Will emerge naturally from tests in issues #7-12.

6. **OwnerFactory**: Not needed as a separate class — `UserFactory` already defaults to `Role.OWNER`. Add an alias `OwnerFactory = UserFactory` for readability.

7. **AdminFactory**: Add for completeness (three roles = three factories).

8. **Directory scaffold**: Create `__init__.py` for all app test dirs now. Only add `test_models.py` for `accounts` (the only app with a model).

## Implementation Steps

### Step 1: Add pytest-xdist to requirements

**File:** `requirements/local.txt`

```
pytest-xdist>=3.5
```

Rebuild container: `make build` or `docker compose build web`.

### Step 2: Configure coverage in pyproject.toml

**File:** `pyproject.toml`

```toml
[tool.coverage.run]
source = ["apps"]
omit = [
    "*/migrations/*",
    "*/tests/*",
    "*/__init__.py",
]

[tool.coverage.report]
show_missing = true
skip_empty = true
```

Leave `addopts` as-is (no `--cov`). Coverage runs explicitly via `make coverage`.

### Step 3: Add Makefile targets

**File:** `Makefile`

```makefile
coverage:  ## Run tests with coverage report
	docker compose exec web pytest --cov=apps --cov-report=term-missing $(ARGS)
```

### Step 4: Update factories.py

**File:** `tests/factories.py`

Add `AdminFactory` and `OwnerFactory` alias:

```python
import factory
from apps.accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    role = User.Role.OWNER

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "testpass123")
        if create:
            self.save(update_fields=["password"])


class InspectorFactory(UserFactory):
    role = User.Role.INSPECTOR


class AdminFactory(UserFactory):
    role = User.Role.ADMIN


# Alias for readability — UserFactory already defaults to OWNER
OwnerFactory = UserFactory
```

### Step 5: Update conftest.py to use factories

**File:** `tests/conftest.py`

```python
import pytest

from tests.factories import AdminFactory, InspectorFactory, UserFactory


@pytest.fixture
def user():
    """Owner user (default role)."""
    return UserFactory()


@pytest.fixture
def inspector():
    """Inspector user."""
    return InspectorFactory()


@pytest.fixture
def admin_user():
    """Admin user."""
    return AdminFactory()
```

### Step 6: Create test directory structure

```
tests/
├── __init__.py          # existing
├── conftest.py          # updated in step 5
├── factories.py         # updated in step 4
├── accounts/
│   ├── __init__.py
│   └── test_models.py   # smoke test (step 7)
├── apartments/
│   └── __init__.py
├── inspections/
│   └── __init__.py
├── reports/
│   └── __init__.py
├── dashboard/
│   └── __init__.py
├── public/
│   └── __init__.py
└── e2e/
    └── README.md        # existing
```

### Step 7: Write smoke tests

**File:** `tests/accounts/test_models.py`

```python
from apps.accounts.models import User
from tests.factories import AdminFactory, InspectorFactory, UserFactory


class TestUserModel:
    def test_create_user(self, db):
        user = UserFactory()
        assert user.pk is not None
        assert user.role == User.Role.OWNER

    def test_owner_property(self, db):
        user = UserFactory()
        assert user.is_owner is True
        assert user.is_inspector is False

    def test_inspector_property(self, db):
        inspector = InspectorFactory()
        assert inspector.is_inspector is True
        assert inspector.is_owner is False

    def test_admin_factory(self, db):
        admin = AdminFactory()
        assert admin.role == User.Role.ADMIN

    def test_user_str(self, db):
        user = UserFactory(username="testuser")
        assert str(user) == "testuser"
```

## Acceptance Criteria Verification

| Criterion | How to verify |
|-----------|---------------|
| pytest runs and passes | `make test` — should show 5 passing tests |
| Factories generate valid test data | Smoke tests exercise all three factories |
| Coverage report generated on test run | `make coverage` — shows coverage table |
| `make test` shortcut works | Already works, unchanged |

## Out of Scope

- `ApartmentFactory`, `InspectionFactory` — blocked by #7 (core models)
- Base test classes — deferred until patterns emerge
- E2E test setup — separate issue
- CI integration — issue #6

## Sources

- Issue: [#5](https://github.com/robert197/baky/issues/5)
- Roadmap: [#44](https://github.com/robert197/baky/issues/44)
- Existing factories: `tests/factories.py`
- Existing config: `pyproject.toml` pytest section
