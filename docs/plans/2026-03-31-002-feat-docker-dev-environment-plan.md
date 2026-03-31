---
title: "feat: Docker development environment"
type: feat
status: active
date: 2026-03-31
issue: "#3"
---

# Docker Development Environment

## Overview

Set up Docker as the single entry point for development, testing, and production. Docker is the only prerequisite — no local Python, pip, or Node installs required. This issue creates the Dockerfile, docker-compose.yml, Makefile, and minimal Tailwind infrastructure.

## Key Decisions

1. **Tailwind infrastructure**: Create minimal setup in this issue (package.json, tailwind.config.js, input.css) since `tailwind` is one of the 6 required docker-compose services. Without it, `make up` would fail.

2. **Redis**: Drop from docker-compose. Django-Q2 is configured with ORM broker (`"orm": "default"`). Redis can be added later when actually needed. YAGNI.

3. **Production image size**: Accept ~400-500MB due to WeasyPrint system dependencies (libpango, libcairo, etc.). The "<200MB" target from the issue is not achievable with WeasyPrint on Debian. Alpine is not viable (WeasyPrint doesn't build cleanly on musl libc).

4. **Dev server**: Use `runserver` for dev (simpler, built-in reload). Gunicorn only in production stage.

5. **docker-compose.prod.yml**: Defer to issue #41 (production deployment). Only create dev docker-compose.yml.

6. **DATABASE_URL**: Set directly in docker-compose.yml environment section so it works without any `.env` file.

7. **Volume cleanup**: `make down` preserves volumes. Add `make clean` for full reset (`down -v`).

8. **Mailpit integration**: Update `local.py` to use SMTP backend pointing to Mailpit when `EMAIL_HOST` env var is set.

9. **Debug toolbar in Docker**: Fix `INTERNAL_IPS` with a `show_toolbar` callback that works with Docker's gateway IPs.

10. **CI**: Dev image target runs tests/lint. Production image target builds for deployment. Actual GitHub Actions config deferred to issue #6.

## Proposed Solution

### Task 1: Create Dockerfile (multi-stage)

**File**: `Dockerfile`

```dockerfile
# Stage 1: Base — system dependencies for WeasyPrint/Pillow
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango1.0-dev \
    libcairo2-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Stage 2: Dev
FROM base AS dev

COPY requirements/base.txt requirements/base.txt
COPY requirements/local.txt requirements/local.txt
RUN pip install --no-cache-dir -r requirements/local.txt

ENV DJANGO_SETTINGS_MODULE=baky.settings.local

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Stage 3: Production
FROM base AS production

COPY requirements/base.txt requirements/base.txt
COPY requirements/production.txt requirements/production.txt
RUN pip install --no-cache-dir -r requirements/production.txt

# Remove build-essential after pip install to reduce image size
RUN apt-get purge -y build-essential && apt-get autoremove -y

COPY . .

RUN addgroup --system django && adduser --system --ingroup django django
RUN python manage.py collectstatic --noinput

ENV DJANGO_SETTINGS_MODULE=baky.settings.production
USER django

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -f http://localhost:8000/ || exit 1

EXPOSE 8000
CMD ["gunicorn", "baky.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

### Task 2: Create docker-compose.yml

**File**: `docker-compose.yml`

5 services (Redis dropped):

```yaml
services:
  web:
    build:
      context: .
      target: dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgres://baky:baky@db:5432/baky
      - SECRET_KEY=django-insecure-docker-dev-key
      - DEBUG=True
      - ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
      - EMAIL_HOST=mailpit
      - EMAIL_PORT=1025
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=baky
      - POSTGRES_USER=baky
      - POSTGRES_PASSWORD=baky
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U baky"]
      interval: 5s
      timeout: 3s
      retries: 5

  worker:
    build:
      context: .
      target: dev
    command: python manage.py qcluster
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgres://baky:baky@db:5432/baky
      - SECRET_KEY=django-insecure-docker-dev-key
      - DEBUG=True
    depends_on:
      db:
        condition: service_healthy

  tailwind:
    image: node:20-slim
    working_dir: /app
    volumes:
      - .:/app
    command: npx tailwindcss -i static/css/input.css -o static/css/output.css --watch
    # depends on package.json and tailwind.config.js existing

  mailpit:
    image: axllent/mailpit
    ports:
      - "8025:8025"  # Web UI
      - "1025:1025"  # SMTP
```

Key points:
- PostgreSQL has a healthcheck so `depends_on: condition: service_healthy` works
- DB exposed on 5432 for GUI tools (pgAdmin, TablePlus)
- Mailpit UI on 8025, SMTP on 1025
- Named volume `postgres_data` for DB persistence

### Task 3: Create Makefile

**File**: `Makefile`

```makefile
.PHONY: up down build migrate makemigrations test lint shell dbshell \
        createsuperuser seed logs manage e2e validate clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

test:
	docker compose exec web pytest $(ARGS)

lint:
	docker compose exec web ruff check . && docker compose exec web ruff format --check .

shell:
	docker compose exec web python manage.py shell

dbshell:
	docker compose exec db psql -U baky -d baky

createsuperuser:
	docker compose exec web python manage.py createsuperuser

seed:
	docker compose exec web python manage.py seed_all

logs:
	docker compose logs -f

manage:
	docker compose exec web python manage.py $(CMD)

e2e:
	@echo "E2E tests not yet configured (see issue #5)"

validate:
	$(MAKE) lint
	$(MAKE) test

clean:
	docker compose down -v
```

### Task 4: Create .dockerignore

**File**: `.dockerignore`

```
.git
__pycache__
*.pyc
*.pyo
*.egg-info
dist
build
node_modules
.venv
venv
media
db.sqlite3
db.sqlite3-journal
staticfiles
.env
.env.local
.env.production
.ruff_cache
.pytest_cache
.mypy_cache
.coverage
htmlcov
.docker
.DS_Store
.idea
.vscode
*.swp
*.swo
docs
tests/e2e/screenshots
tests/e2e/videos
test-results
.claude
.ralph
```

### Task 5: Create minimal Tailwind infrastructure

**Files**: `package.json`, `tailwind.config.js`, `static/css/input.css`

`package.json`:
```json
{
  "private": true,
  "devDependencies": {
    "tailwindcss": "^3.4"
  }
}
```

`tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1e293b", // slate-800
        },
        accent: {
          DEFAULT: "#f59e0b", // amber-500
        },
      },
    },
  },
  plugins: [],
};
```

`static/css/input.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### Task 6: Update local.py for Mailpit and Docker debug toolbar

**File**: `baky/settings/local.py`

```python
# Email — use Mailpit SMTP when EMAIL_HOST is set (Docker), else console
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa: F405
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env.int("EMAIL_PORT", default=1025)  # noqa: F405
    EMAIL_USE_TLS = False
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Debug toolbar — show for Docker gateway IPs too
import socket  # noqa: E402
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]  # noqa: F405
```

### Task 7: Update .env.example with Docker DATABASE_URL

**File**: `.env.example`

Add a comment to the DATABASE_URL section noting the Docker default:

```bash
# PostgreSQL connection string. Falls back to SQLite in local dev.
# Format: postgres://USER:PASSWORD@HOST:PORT/NAME
# Docker default (set in docker-compose.yml): postgres://baky:baky@db:5432/baky
# DATABASE_URL=postgres://baky:baky@localhost:5432/baky
```

## Acceptance Criteria

- [ ] `make up` starts all services from scratch (zero local deps besides Docker)
- [ ] Code changes reflect immediately (hot reload via volume mount + runserver)
- [ ] Database persists between restarts (named volume `postgres_data`)
- [ ] Email sending works locally via Mailpit (UI at localhost:8025)
- [ ] Background worker processes tasks (`make manage CMD="qinfo"` shows cluster)
- [ ] Tailwind rebuilds on template changes
- [ ] `make test` runs full test suite inside container
- [ ] `make lint` runs ruff inside container
- [ ] Production image builds correctly (`docker build --target production .`)
- [ ] `make clean` destroys volumes for fresh start
- [ ] PostgreSQL healthcheck ensures web/worker wait for DB readiness
- [ ] Debug toolbar works inside Docker

## Port Map

| Port | Service | Purpose |
|------|---------|---------|
| 8000 | web | Django app |
| 5432 | db | PostgreSQL (for GUI tools) |
| 8025 | mailpit | Email web UI |
| 1025 | mailpit | SMTP |

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage: base → dev → production |
| `docker-compose.yml` | 5 services: web, db, worker, tailwind, mailpit |
| `Makefile` | Developer CLI wrapping docker compose |
| `.dockerignore` | Exclude unnecessary files from build context |
| `package.json` | Tailwind CSS dependency |
| `tailwind.config.js` | Tailwind content paths and theme config |
| `static/css/input.css` | Tailwind directives |
| `baky/settings/local.py` | Mailpit email + debug toolbar Docker fix |
| `.env.example` | Updated with Docker DATABASE_URL comment |

## Sources

- Issue: [#3](https://github.com/robert197/baky/issues/3)
- Roadmap: [#44](https://github.com/robert197/baky/issues/44)
- CLAUDE.md: Tech stack, Makefile targets, design tokens
