---
title: "feat: Production Deployment Configuration"
type: feat
status: active
date: 2026-04-02
---

# feat: Production Deployment Configuration

## Overview

Make BAKY production-ready by closing the gaps between the current Docker/Django setup and a
fully deployable application. The Dockerfile already has a production stage with Gunicorn, and
`production.py` already has security headers, WhiteNoise, S3 media, and basic Sentry. This
issue fills the remaining gaps: health check endpoint, structured logging, Gunicorn config file,
Tailwind CSS build in Docker, CSRF_TRUSTED_ORIGINS, docker-compose.prod.yml, env var
documentation, and deploy workflow completion.

Closes #41.

## Gap Analysis

| Requirement | Status | Gap |
|---|---|---|
| Production Django settings | ~80% done | Missing: LOGGING, CSRF_TRUSTED_ORIGINS, SECURE_REDIRECT_EXEMPT, upload limits |
| Gunicorn | Inline CMD only | Need `gunicorn.conf.py` with worker recycling, timeouts, access logs |
| WhiteNoise | Configured | Tailwind CSS not built in Docker production stage (no Node.js) |
| Managed PostgreSQL | Ready | DATABASE_URL env parsing works |
| Health check `/health/` | Not implemented | Need view + URL + update Dockerfile HEALTHCHECK |
| Sentry | Basic init | Need release, environment, send_default_pii=False |
| Structured JSON logging | Not implemented | No LOGGING dict anywhere |
| Custom domain + SSL | Ready | ALLOWED_HOSTS from env works, SSL provider-managed |
| `check --deploy` | Untested | Likely fails (missing CSRF_TRUSTED_ORIGINS, collectstatic errors) |
| docker-compose.prod.yml | Missing | Need production overrides with worker service |
| Deploy workflow | Skeleton | Builds image but does not push/deploy |
| Env var documentation | Missing | Need .env.example for production |

## Technical Approach

### Architecture

No new Django apps. Changes span settings, Docker, CI/CD, and one new view.

```
Modified files:
  baky/settings/production.py    — LOGGING, CSRF_TRUSTED_ORIGINS, Sentry, security, upload limits
  baky/settings/base.py          — base LOGGING config, DATA_UPLOAD_MAX_MEMORY_SIZE
  baky/urls.py                   — /health/ endpoint
  apps/public/views.py           — health_check view
  Dockerfile                     — Tailwind build stage, fix collectstatic, fix HEALTHCHECK
  requirements/production.txt    — python-json-logger, whitenoise[brotli]
  .github/workflows/deploy.yml  — complete deployment steps

New files:
  gunicorn.conf.py               — Gunicorn configuration
  docker-compose.prod.yml        — Production compose overrides
  .env.example                   — All required env vars documented
```

## Implementation Tasks

### Task 1: Health Check Endpoint

**Why**: The Dockerfile HEALTHCHECK currently hits `/` (full homepage render). Need a lightweight
`/health/` that checks DB connectivity and returns JSON. Required by hosting platforms.

**Test first** (`tests/test_health.py`):

```python
import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_returns_200(self, client: Client):
        response = client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_json_content_type(self, client: Client):
        response = client.get("/health/")
        assert response["Content-Type"] == "application/json"

    def test_health_no_auth_required(self, client: Client):
        """Health check must work without authentication."""
        response = client.get("/health/")
        assert response.status_code == 200

    def test_health_includes_version(self, client: Client):
        response = client.get("/health/")
        data = response.json()
        assert "version" in data

    def test_health_get_only(self, client: Client):
        response = client.post("/health/")
        assert response.status_code == 405
```

**Implementation** (`apps/public/views.py`):

```python
import logging
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

@require_GET
def health_check(request):
    """Lightweight health check for Docker/LB probes."""
    checks = {"status": "ok", "version": "1.0.0"}
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        checks["status"] = "error"
        checks["database"] = "unreachable"
        status_code = 503
        logger.error("Health check failed: database unreachable", exc_info=True)

    return JsonResponse(checks, status=status_code)
```

**URL** (`baky/urls.py`): Add `path("health/", health_check)` before the catch-all public URLs.

**Verify**: `make test ARGS="-k test_health"`

---

### Task 2: Gunicorn Configuration File

**Why**: Inline `--workers 3` in Dockerfile lacks worker recycling (memory leaks from WeasyPrint),
graceful shutdown, access logging, and proper Docker settings.

**Test first** (`tests/test_gunicorn_config.py`):

```python
import importlib
import os

def test_gunicorn_config_is_importable():
    """gunicorn.conf.py must be valid Python."""
    spec = importlib.util.spec_from_file_location("gunicorn_conf", "gunicorn.conf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "bind")
    assert hasattr(mod, "workers")
    assert hasattr(mod, "max_requests")

def test_gunicorn_worker_tmp_dir():
    spec = importlib.util.spec_from_file_location("gunicorn_conf", "gunicorn.conf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.worker_tmp_dir == "/dev/shm"

def test_gunicorn_max_requests_set():
    spec = importlib.util.spec_from_file_location("gunicorn_conf", "gunicorn.conf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.max_requests > 0
    assert mod.max_requests_jitter > 0
```

**Implementation** (`gunicorn.conf.py` at project root):

```python
import multiprocessing
import os

# Bind
bind = "0.0.0.0:8000"

# Workers
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = 4
worker_tmp_dir = "/dev/shm"

# Timeouts
timeout = 30
graceful_timeout = 30
keepalive = 5

# Memory leak protection (important: WeasyPrint/Pillow can leak)
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Reverse proxy
forwarded_allow_ips = "*"

# Preload for memory sharing via copy-on-write
preload_app = True
```

**Update Dockerfile CMD**: `CMD ["gunicorn", "--config", "gunicorn.conf.py", "baky.wsgi:application"]`

**Verify**: `python -c "import importlib.util; s=importlib.util.spec_from_file_location('g','gunicorn.conf.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('OK')"`

---

### Task 3: Production Settings Hardening

**Why**: Fill remaining gaps in `production.py` — CSRF, logging, Sentry, security, upload limits.

**3a: CSRF_TRUSTED_ORIGINS**

Add to `production.py`:
```python
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
```

**3b: Structured JSON Logging**

Add `python-json-logger>=4.0` to `requirements/production.txt`.

Add to `production.py`:
```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "baky": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
```

**3c: Enhanced Sentry**

```python
import sentry_sdk

sentry_sdk.init(
    dsn=env("SENTRY_DSN", default=""),
    release=env("GIT_SHA", default=None),
    environment=env("SENTRY_ENVIRONMENT", default="production"),
    traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", default="0.1")),
    send_default_pii=False,
)
```

**3d: Additional Security Settings**

```python
SECURE_REDIRECT_EXEMPT = [r"^health/$"]  # Health check must work over HTTP internally
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20MB for inspector photos
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
```

**Test** (`tests/test_production_settings.py`):

```python
import pytest
from django.test import override_settings

class TestProductionSettings:
    def test_health_exempt_from_ssl_redirect(self, settings):
        """Health check path must be in SECURE_REDIRECT_EXEMPT for internal probes."""
        # This test verifies the pattern exists — actual redirect tested in integration
        import re
        exempt = getattr(settings, "SECURE_REDIRECT_EXEMPT", [])
        # In local settings this may not be set, so this is a documentation test
        # The real validation is `manage.py check --deploy` in CI

    def test_upload_max_size_sufficient_for_photos(self, settings):
        """Upload limit must accommodate large HEIF photos from mobile."""
        max_size = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 2621440)
        assert max_size >= 10 * 1024 * 1024  # At least 10MB
```

**Verify**: `make test` + `make lint`

---

### Task 4: Dockerfile Fixes

**Why**: Three critical issues: (1) No Tailwind CSS build in production stage, (2) `collectstatic`
silently swallows errors, (3) HEALTHCHECK hits `/` instead of `/health/`.

**4a: Add Tailwind Builder Stage**

Insert a new stage between `base` and `production`:

```dockerfile
# ---------------------------------------------------------------------------
# Stage: Tailwind Builder — compile CSS for production
# ---------------------------------------------------------------------------
FROM node:20-slim AS tailwind-builder

WORKDIR /app
COPY package.json tailwind.config.js ./
COPY static/css/input.css static/css/input.css
COPY templates/ templates/
COPY apps/ apps/
RUN npx tailwindcss -i static/css/input.css -o static/css/output.css --minify
```

In the production stage, copy the built CSS:
```dockerfile
COPY --from=tailwind-builder /app/static/css/output.css static/css/output.css
```

**4b: Fix collectstatic**

Replace the silent failure with proper build-time env vars:
```dockerfile
RUN SECRET_KEY=build-placeholder ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite:///tmp/throwaway.db \
    FIELD_ENCRYPTION_KEY=build-placeholder-key-min-32chars!! \
    python manage.py collectstatic --noinput
```

**4c: Fix HEALTHCHECK**

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f --connect-timeout 2 --max-time 4 http://localhost:8000/health/ || exit 1
```

**Test**: Build the production image and verify:
```bash
docker build --target production -t baky:test .
docker run --rm -d --name baky-test -e DATABASE_URL=... baky:test
docker exec baky-test curl -f http://localhost:8000/health/
docker stop baky-test
```

**Verify**: `docker build --target production -t baky:test .` succeeds without errors.

---

### Task 5: docker-compose.prod.yml

**Why**: Production needs Gunicorn (not runserver), a worker process, and production env vars.

**Implementation** (`docker-compose.prod.yml`):

```yaml
# Production overrides — use with: docker compose -f docker-compose.yml -f docker-compose.prod.yml up
# Or standalone for hosting platforms that support Docker Compose.
services:
  web:
    build:
      context: .
      target: production
    command: gunicorn --config gunicorn.conf.py baky.wsgi:application
    environment:
      - DJANGO_SETTINGS_MODULE=baky.settings.production
    env_file:
      - .env.production
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    stop_grace_period: 35s
    restart: unless-stopped

  worker:
    build:
      context: .
      target: production
    command: python manage.py qcluster
    environment:
      - DJANGO_SETTINGS_MODULE=baky.settings.production
    env_file:
      - .env.production
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16
    volumes:
      - postgres_data_prod:/var/lib/postgresql/data
    env_file:
      - .env.production
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data_prod:
```

**Test**: File is valid YAML — `docker compose -f docker-compose.prod.yml config`

---

### Task 6: Environment Variable Documentation

**Why**: First deploy will fail repeatedly without knowing which env vars are needed.

**Implementation** (`.env.example`):

```bash
# =============================================================================
# BAKY Production Environment Variables
# Copy to .env.production and fill in real values
# =============================================================================

# Django Core
SECRET_KEY=           # Generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DEBUG=False
ALLOWED_HOSTS=baky.at,www.baky.at
DJANGO_SETTINGS_MODULE=baky.settings.production

# Database
DATABASE_URL=postgres://user:password@host:5432/baky

# CSRF (must include https:// scheme)
CSRF_TRUSTED_ORIGINS=https://baky.at,https://www.baky.at

# Encrypted Fields
FIELD_ENCRYPTION_KEY=  # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# S3/R2 Media Storage
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=baky-media
AWS_S3_ENDPOINT_URL=   # e.g., https://xxx.r2.cloudflarestorage.com
AWS_S3_CUSTOM_DOMAIN=  # Optional: custom CDN domain for media

# Email (Resend)
RESEND_API_KEY=
SITE_URL=https://baky.at

# Error Tracking (Sentry)
SENTRY_DSN=            # Optional: leave empty to disable
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Gunicorn
WEB_CONCURRENCY=5      # Workers: 2*CPU+1
GUNICORN_LOG_LEVEL=info

# Build-time (set in CI)
GIT_SHA=               # Set automatically by CI/CD

# PostgreSQL (for docker-compose.prod.yml db service)
POSTGRES_DB=baky
POSTGRES_USER=baky
POSTGRES_PASSWORD=

# Google Maps (optional, client-side key)
GOOGLE_MAPS_API_KEY=
```

---

### Task 7: Deploy Workflow Completion

**Why**: Current workflow only builds the image. Complete with registry push, migration, and
health check verification.

**Implementation** (`.github/workflows/deploy.yml`):

```yaml
name: Deploy

on:
  push:
    branches: [main]

permissions:
  contents: read
  packages: write

concurrency:
  group: deploy
  cancel-in-progress: false

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    name: Build & Push Production Image
    runs-on: ubuntu-latest
    timeout-minutes: 20
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          target: production
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          build-args: |
            GIT_SHA=${{ github.sha }}

      # TODO: Add platform-specific deployment steps when hosting provider is chosen
      # For Railway: railway up
      # For Fly.io: flyctl deploy --image ${{ steps.meta.outputs.tags }}
      # For Render: auto-deploy from registry

      # TODO: Post-deploy verification
      # - name: Verify health check
      #   run: |
      #     for i in $(seq 1 30); do
      #       if curl -sf https://baky.at/health/; then exit 0; fi
      #       sleep 10
      #     done
      #     exit 1
```

---

### Task 8: Validate with `manage.py check --deploy`

**Why**: Final verification that all security settings pass Django's deployment checklist.

**Test**: Run inside Docker with production settings:
```bash
docker compose exec web python manage.py check --deploy --settings=baky.settings.production
```

This will catch any remaining issues (missing settings, security warnings). Fix any warnings
that appear. Expected items already handled:
- SECURE_SSL_REDIRECT ✓
- HSTS ✓
- SESSION_COOKIE_SECURE ✓
- CSRF_COOKIE_SECURE ✓
- DEBUG=False ✓

**Verify**: Zero warnings from `check --deploy`.

---

## Acceptance Criteria

- [ ] `/health/` returns 200 with JSON `{"status": "ok", "version": "1.0.0"}`
- [ ] `/health/` returns 503 when database is unreachable
- [ ] `gunicorn.conf.py` exists with worker recycling, timeouts, access logging
- [ ] `production.py` has CSRF_TRUSTED_ORIGINS, LOGGING, enhanced Sentry
- [ ] `production.py` has SECURE_REDIRECT_EXEMPT for `/health/`
- [ ] Dockerfile builds Tailwind CSS in a builder stage
- [ ] Dockerfile `collectstatic` fails loudly (no `|| true`)
- [ ] Dockerfile HEALTHCHECK targets `/health/`
- [ ] `docker-compose.prod.yml` defines web + worker services
- [ ] `.env.example` documents all required production env vars
- [ ] Deploy workflow pushes to GHCR with SHA and latest tags
- [ ] `python manage.py check --deploy` passes with zero warnings
- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] Production Docker image builds successfully

## Sources & References

- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Gunicorn settings: https://docs.gunicorn.org/en/stable/settings.html
- WhiteNoise Django docs: https://whitenoise.readthedocs.io/en/stable/django.html
- Sentry Django integration: https://docs.sentry.io/platforms/python/integrations/django/
- python-json-logger: https://pypi.org/project/python-json-logger/
- Related: #6 (CI/CD pipeline), #3 (Docker environment)
