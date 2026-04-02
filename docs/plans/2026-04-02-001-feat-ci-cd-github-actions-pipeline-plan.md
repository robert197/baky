---
title: "feat: Configure CI/CD pipeline with GitHub Actions"
type: feat
status: active
date: 2026-04-02
---

# Configure CI/CD pipeline with GitHub Actions

## Overview

Set up GitHub Actions workflows for automated testing, linting, and deployment of the BAKY Django project. The CI pipeline runs on every PR and push to main, ensuring code quality gates are enforced. The CD pipeline builds the production Docker image on merge to main (deploy target TBD).

## Problem Statement / Motivation

Currently there are no automated checks — code quality depends entirely on local discipline (`make lint`, `make test`). A CI pipeline enforces the same validation gates defined in the Makefile automatically on every PR, preventing regressions and maintaining code quality as the team scales.

## Proposed Solution

Two GitHub Actions workflow files:

1. **`.github/workflows/ci.yml`** — Runs on PR and push to main. Three parallel jobs:
   - **Lint**: ruff check, ruff format check, djlint lint, djlint format check
   - **Test**: pytest with PostgreSQL 16 service container, coverage report, migration check, Django system check
   - **E2E**: pytest e2e tests with Playwright Chromium (separate job due to heavy dependencies)

2. **`.github/workflows/deploy.yml`** — Runs on push to main only. Builds production Docker image. Placeholder for actual deployment when hosting provider is chosen.

### Architecture Decision: Direct execution vs Docker-in-CI

**Chosen: Direct execution on ubuntu-latest** (not running inside Docker containers in CI).

Rationale:
- Standard GitHub Actions pattern — faster startup, native caching
- PostgreSQL service container is natively supported
- Avoids Docker-in-Docker complexity
- Lint job needs only pip packages (fast, no system deps)
- Test/E2E jobs install system deps from Dockerfile's apt-get list

The Makefile targets (`make lint`, `make test`) use `docker compose exec` which requires running containers — CI runs commands directly instead, mirroring the same underlying commands.

## Technical Considerations

- **System dependencies**: WeasyPrint requires `libpango1.0-dev`, `libcairo2-dev`, `libgdk-pixbuf-2.0-dev`, `libffi-dev`, `shared-mime-info`, `fonts-liberation`. Pillow needs `libjpeg62-turbo-dev`, `zlib1g-dev`. PostgreSQL client needs `libpq-dev`.
- **No Redis needed**: Django-Q2 uses ORM broker, not Redis.
- **`--reuse-db` override**: pytest addopts includes `--reuse-db`. CI should use `--create-db` to ensure clean state.
- **`--cov` not in addopts**: Coverage is intentionally excluded from default pytest config (keeps local TDD fast). CI adds it explicitly.
- **`pytest-xdist`**: Available for parallel test execution (`-n auto`), but skip for now to keep CI simple and debuggable.
- **Tailwind CSS**: `static/css/output.css` is gitignored. E2E tests using `live_server` need compiled CSS. The e2e job must build Tailwind first.
- **Settings module**: `baky.settings.local` provides safe defaults for SECRET_KEY, FIELD_ENCRYPTION_KEY, ALLOWED_HOSTS — no secrets needed in CI env vars.

## Acceptance Criteria

- [x] CI runs automatically on PR creation and push to main
- [x] Lint job: ruff check, ruff format --check, djlint --lint, djlint --check
- [x] Test job: pytest with PostgreSQL 16 service container
- [x] Coverage report generated and uploaded as artifact
- [x] `python manage.py check` runs in CI
- [x] `python manage.py makemigrations --check --dry-run` verifies migrations are up to date
- [x] Deploy workflow builds production Docker image on merge to main
- [x] Failed CI blocks merge (branch protection documentation provided)

## Implementation Tasks

### Task 1: Create CI workflow — Lint job

**File**: `.github/workflows/ci.yml`

Create the workflow file with the lint job. This job is fast (no database, no system deps) and runs the same four commands as `make lint`.

**Test**: Push branch, verify lint job runs and passes. Locally verify:
```bash
ruff check . && ruff format --check . && djlint templates/ --lint && djlint templates/ --check
```

**Implementation**:
```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install linting tools
        run: pip install ruff djlint

      - name: Ruff check
        run: ruff check .

      - name: Ruff format check
        run: ruff format --check .

      - name: djlint lint
        run: djlint templates/ --lint

      - name: djlint format check
        run: djlint templates/ --check
```

### Task 2: Add Test job to CI workflow

**File**: `.github/workflows/ci.yml` (extend)

Add the test job with PostgreSQL 16 service container. Installs system dependencies for WeasyPrint/Pillow, runs Django checks, migration check, and pytest with coverage.

**Test**: Push branch, verify test job runs with PostgreSQL and passes. Locally verify:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest --ignore=tests/e2e --create-db --cov=apps --cov-report=term-missing
```

**Implementation** (add to ci.yml):
```yaml
  test:
    name: Test
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: baky
          POSTGRES_PASSWORD: baky
          POSTGRES_DB: baky
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U baky"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      DATABASE_URL: postgres://baky:baky@localhost:5432/baky
      DJANGO_SETTINGS_MODULE: baky.settings.local

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements/local.txt

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            libpango1.0-dev libcairo2-dev libgdk-pixbuf-2.0-dev \
            libffi-dev shared-mime-info fonts-liberation \
            libjpeg62-turbo-dev zlib1g-dev libpq-dev

      - name: Install Python dependencies
        run: pip install -r requirements/local.txt

      - name: Django system check
        run: python manage.py check

      - name: Check migrations
        run: python manage.py makemigrations --check --dry-run

      - name: Run tests with coverage
        run: >-
          pytest --ignore=tests/e2e
          --create-db
          --cov=apps
          --cov-report=term-missing
          --cov-report=xml

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml
          retention-days: 30
```

### Task 3: Create deploy workflow

**File**: `.github/workflows/deploy.yml`

Placeholder deploy workflow that builds the production Docker image on merge to main. Actual deployment steps to be added when hosting provider is chosen.

**Test**: Verify YAML is valid and Docker build command references correct Dockerfile target.

**Implementation**:
```yaml
name: Deploy

on:
  push:
    branches: [main]

concurrency:
  group: deploy
  cancel-in-progress: false

jobs:
  build:
    name: Build Production Image
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build production Docker image
        run: docker build --target production -t baky:${{ github.sha }} .

      # TODO: Add deployment steps when hosting provider is chosen
      # Options: Railway, Render, Fly.io
      # Steps needed:
      #   1. Push image to container registry
      #   2. Deploy to hosting platform
      #   3. Run migrations: python manage.py migrate --noinput
      #   4. Collect static files: python manage.py collectstatic --noinput
```

### Task 4: Verify CI works end-to-end

Push the branch and verify:
1. CI workflow triggers on the PR
2. Lint job passes
3. Test job passes with PostgreSQL
4. Coverage artifact is uploaded
5. Deploy workflow does NOT trigger on PR (only push to main)

**Verification commands** (local):
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"

# Verify the same commands work locally
make lint
make test
```

## Dependencies & Risks

- **System deps availability**: Ubuntu runner's apt repos should have all WeasyPrint deps. If `libjpeg62-turbo-dev` isn't available on the runner, fall back to `libjpeg-dev`.
- **CI minutes**: GitHub free tier provides 2,000 minutes/month. The lint job should be <1 min, test job <3 min.
- **Branch protection**: Must be configured manually in GitHub repo settings (Settings → Branches → Add rule for `main` → Require status checks).

## Sources & References

- Existing Makefile quality targets: `Makefile:62-77`
- pytest configuration: `pyproject.toml:26-31`
- Coverage configuration: `pyproject.toml:33-43`
- Ruff configuration: `pyproject.toml:7-17`
- djlint configuration: `pyproject.toml:19-24`
- Dockerfile system deps: `Dockerfile:16-33`
- Docker compose services: `docker-compose.yml`
- Django settings (local): `baky/settings/local.py`
- Related: GitHub issue #6
