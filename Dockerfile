# =============================================================================
# BAKY Dockerfile — Multi-stage build
# Stages: base (system deps) → dev (local dev) → production (slim deploy)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Base — Python + system dependencies for WeasyPrint/Pillow
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint dependencies
    libpango1.0-dev \
    libcairo2-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    # Pillow dependencies
    libjpeg62-turbo-dev \
    zlib1g-dev \
    # PostgreSQL client library
    libpq-dev \
    # Build tools (for compiling Python packages)
    build-essential \
    # Useful utilities
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Stage 2: Dev — local development with debug tools
# ---------------------------------------------------------------------------
FROM base AS dev

COPY requirements/base.txt requirements/base.txt
COPY requirements/local.txt requirements/local.txt
RUN pip install -r requirements/local.txt

# Install Playwright browsers for e2e tests
RUN playwright install --with-deps chromium

ENV DJANGO_SETTINGS_MODULE=baky.settings.local

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------------------------------------------------------------------------
# Stage 3: Production — slim, secure, ready to deploy
# ---------------------------------------------------------------------------
FROM base AS production

COPY requirements/base.txt requirements/base.txt
COPY requirements/production.txt requirements/production.txt
RUN pip install -r requirements/production.txt

# Remove build tools to reduce image size
RUN apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Create non-root user
RUN addgroup --system django && adduser --system --ingroup django django

# Collect static files
ENV DJANGO_SETTINGS_MODULE=baky.settings.production
RUN SECRET_KEY=build-placeholder ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput 2>/dev/null || true

USER django

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -f http://localhost:8000/ || exit 1

EXPOSE 8000
CMD ["gunicorn", "baky.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
