---
title: "feat: Environment and secrets management"
type: feat
status: completed
date: 2026-03-31
issue: "#29"
---

# Environment and Secrets Management

## Overview

Configure proper environment variable and secrets management for BAKY. `django-environ` is already installed and partially wired up, but the project lacks a `.env.example` file, has inconsistent validation, and some variables from the issue spec are not yet in settings.

## Current State

- `django-environ` is in `requirements/base.txt` and used in `base.py`, `local.py`, `production.py`
- `.gitignore` already excludes `.env`, `.env.local`, `.env.production`
- No `.env.example` exists
- `SECRET_KEY` has no default -- crashes immediately without it
- `local.py` redundantly re-declares `DATABASES` identically to `base.py`
- Production AWS vars default to empty strings (silent failure at runtime)
- Three variables from the issue (`EMAIL_API_KEY`, `ENCRYPTION_KEY`, `AWS_S3_REGION_NAME`) are not yet in settings
- `read_env()` is called unconditionally -- will fail in CI/production without a `.env` file
- `SENTRY_DSN` is used in `production.py` but not documented

## Key Decisions

1. **Missing `.env` file handling**: Wrap `read_env()` in a file-existence check so CI and production can rely on injected env vars without a `.env` file.

2. **Production required vars**: Remove empty-string defaults from production AWS vars. Production should fail loudly at startup, not silently at runtime when an inspector uploads a photo.

3. **Unimplemented variables**: Only document variables that are actively used in settings. `EMAIL_API_KEY`, `ENCRYPTION_KEY`, and `AWS_S3_REGION_NAME` will NOT be added yet -- they belong to their respective feature issues (#9, #24, #25). Add `# Future:` comments in `.env.example`.

4. **Validation approach**: Use `django-environ`'s built-in `ImproperlyConfigured` (no default = required). This is simple and gives a clear message: `"Set the SECRET_KEY environment variable"`.

5. **Local dev SECRET_KEY**: Add a dev-only default in `local.py` so new developers can start immediately after copying `.env.example`.

6. **Redundant DATABASES in local.py**: Remove it -- `base.py` already handles the SQLite default.

7. **DJANGO_SETTINGS_MODULE**: Document in `.env.example` with a comment that it's already set in `manage.py`/`wsgi.py`. Not truly an env-file variable.

## Proposed Solution

### Task 1: Fix `read_env()` for missing file

**File**: `baky/settings/base.py`

```python
# Before
environ.Env.read_env(BASE_DIR / ".env")

# After
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)
```

### Task 2: Clean up `local.py`

**File**: `baky/settings/local.py`

- Remove redundant `DATABASES` declaration
- Add dev-safe `SECRET_KEY` default:
  ```python
  SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key-not-for-production")
  ```
- Add dev-safe `ALLOWED_HOSTS` default:
  ```python
  ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])
  ```

### Task 3: Harden `production.py`

**File**: `baky/settings/production.py`

- Remove empty-string defaults from required production vars:
  ```python
  # Before
  AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")

  # After
  AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")  # Required in production
  ```
- Ensure `ALLOWED_HOSTS` has no empty-list default in production
- Keep `SENTRY_DSN` optional (with empty default) since monitoring is not strictly required

### Task 4: Create `.env.example`

**File**: `.env.example`

```bash
# =============================================================================
# BAKY Environment Configuration
# Copy this file to .env and fill in your values:
#   cp .env.example .env
# =============================================================================

# -----------------------------------------------------------------------------
# Django Core
# -----------------------------------------------------------------------------
# SECURITY WARNING: Generate a unique key for production!
# Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=

# Set to True for development, False for production
DEBUG=True

# Comma-separated list of hostnames. Required in production.
# Example: ALLOWED_HOSTS=baky.at,www.baky.at
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Which settings module to use (already set in manage.py/wsgi.py as default)
# DJANGO_SETTINGS_MODULE=baky.settings.local

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
# PostgreSQL connection string. Falls back to SQLite in local dev.
# Format: postgres://USER:PASSWORD@HOST:PORT/NAME
# DATABASE_URL=postgres://baky:baky@localhost:5432/baky

# -----------------------------------------------------------------------------
# Storage (AWS S3 / Cloudflare R2) — Production only
# -----------------------------------------------------------------------------
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_STORAGE_BUCKET_NAME=
# AWS_S3_ENDPOINT_URL=
# AWS_S3_CUSTOM_DOMAIN=

# -----------------------------------------------------------------------------
# Monitoring — Production only
# -----------------------------------------------------------------------------
# SENTRY_DSN=

# -----------------------------------------------------------------------------
# Future (not yet wired into settings)
# These will be configured when their features are implemented:
# - EMAIL_API_KEY — Resend API key (issue #24)
# - ENCRYPTION_KEY — django-encrypted-model-fields (issue #25)
# -----------------------------------------------------------------------------
```

### Task 5: Verify acceptance criteria

- [ ] `.env.example` documents all active variables with format examples
- [ ] App starts with only `.env` file (no hardcoded secrets in committed code)
- [ ] Missing required env vars cause clear `ImproperlyConfigured` error messages
- [ ] `.env` is gitignored (already done)
- [ ] App works in CI/production without a `.env` file (env vars injected externally)

## Acceptance Criteria

- [ ] `.env.example` exists with all active variables documented, grouped by concern
- [ ] `read_env()` handles missing `.env` file gracefully
- [ ] `local.py` has dev-safe defaults (SECRET_KEY, ALLOWED_HOSTS, DEBUG)
- [ ] `local.py` does not redundantly declare DATABASES
- [ ] `production.py` requires AWS vars (no empty-string defaults)
- [ ] App starts successfully with `cp .env.example .env` (local dev)
- [ ] Missing required vars in production settings raise clear errors

## Key Files

- `baky/settings/base.py` — `read_env()` fix
- `baky/settings/local.py` — dev defaults, remove redundant DATABASES
- `baky/settings/production.py` — remove empty-string defaults for required vars
- `.env.example` — new file, all documented variables

## Sources

- Issue: [#29](https://github.com/robert197/baky/issues/29)
- Roadmap: [#44](https://github.com/robert197/baky/issues/44)
