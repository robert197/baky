---
name: validate
description: Run the full BAKY validation suite — unit tests, linting, e2e tests, and Django checks. Use after completing any feature to ensure everything works.
user-invokable: true
argument-hint: "[optional: --quick for fast validation, --full for everything including e2e]"
---

# BAKY Validation Suite

## Quick Validation (default, ~30 seconds)

Run after every code change:

```bash
make lint
make test
make manage CMD="check"
```

All three must pass. If any fail, stop and fix.

## Full Validation (--full, ~2 minutes)

Run before merging a feature branch:

```bash
# 1. Lint
make lint

# 2. Unit + integration tests
make test

# 3. Django system checks
make manage CMD="check"

# 4. Migration check (no unapplied migrations)
make manage CMD="showmigrations" | grep -E "^\[.\]" | grep -v "\[X\]"
# Should return nothing (all migrations applied)

# 5. E2E browser tests (if UI changed)
make e2e

# 6. Check no secrets in code
grep -r "password\|secret\|api_key" --include="*.py" -l | grep -v test | grep -v example | grep -v settings
# Should return nothing (no hardcoded secrets)
```

## E2E Test Structure

E2E tests use pytest-playwright and validate complete user flows:

```
tests/e2e/
├── conftest.py          # Playwright fixtures, live server setup
├── test_public.py       # Public pages load, links work, signup flow
├── test_owner.py        # Owner login, dashboard, apartment management
├── test_inspector.py    # Inspector login, schedule, checklist, submit
├── test_reports.py      # Report generated after inspection, email sent
└── test_auth.py         # Login, logout, role separation, 404 on unauthorized
```

## E2E Test Conventions

- Tests run against Django's LiveServerTestCase (real server, real database)
- Seed data loaded before e2e tests via fixture or management command
- Each test class gets a fresh database state
- Tests are independent — no ordering dependency
- Mobile viewport (375x812) for inspector tests
- Desktop viewport (1280x720) for owner/public tests

## Validation Gates for Ralph Autopilot

Ralph MUST run validation at these gates:

| Gate | When | What to Run |
|------|------|-------------|
| Pre-merge | Before merging feature to main | Full validation |
| Post-merge | After merging to main | Quick validation (smoke test) |
| Phase complete | After finishing a roadmap phase | Full validation + e2e |

## What to Do When Validation Fails

1. **Lint fails**: Fix formatting/style issues, re-run
2. **Unit test fails**: Read the error, fix the code or test, re-run
3. **E2E fails**: Check if seed data is correct, check if UI matches selectors, fix
4. **Migration check fails**: Run `make migrate`
5. **Django check fails**: Read the warning, fix the configuration

NEVER merge to main with failing validation. NEVER skip validation to "save time".
