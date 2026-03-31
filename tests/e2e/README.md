# BAKY E2E Tests

End-to-end tests using pytest-playwright. These test complete user flows against a live Django server.

## Setup

E2E tests are part of the Docker test suite:

```bash
make e2e                    # Run all e2e tests
make test ARGS="tests/e2e/" # Same thing
```

## Test Files

| File | What It Tests |
|------|--------------|
| `test_public.py` | Landing page loads, pricing page, legal pages, navigation links |
| `test_auth.py` | Login, logout, role-based redirects, unauthorized access returns 404 |
| `test_signup.py` | Owner signup flow: form → email verification → apartment registration |
| `test_owner.py` | Owner dashboard: apartment list, inspection timeline, report view |
| `test_inspector.py` | Inspector app: schedule view, checklist execution, photo upload, submit |
| `test_reports.py` | Report generation triggered, email sent, report viewable in dashboard |

## Conventions

- Tests use seed data (loaded in conftest.py via `seed_all` management command)
- Mobile viewport (375x812) for inspector tests
- Desktop viewport (1280x720) for owner/public tests
- Each test is independent (no ordering)
- Use `page.goto()` with relative paths
- Assert on visible text content, not CSS selectors when possible
- Screenshots saved on failure for debugging

## Adding New E2E Tests

When implementing a new feature that has a UI:
1. Write the e2e test AFTER unit tests pass
2. The test should verify the complete user flow
3. Use seed data — don't create test data in e2e tests
4. Run `make e2e` to verify

## Dependencies

In `requirements/local.txt`:
```
pytest-playwright
playwright
```

In `Dockerfile`:
```dockerfile
RUN playwright install --with-deps chromium
```
