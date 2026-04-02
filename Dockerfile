# =============================================================================
# BAKY Dockerfile — Multi-stage build
# Stages: base (system deps) → dev (local dev) → tailwind-builder → production
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
# Stage 3: Tailwind Builder — compile CSS for production
# ---------------------------------------------------------------------------
FROM node:20-slim AS tailwind-builder

WORKDIR /app
COPY package.json tailwind.config.js ./
RUN npm install --production=false
COPY static/css/input.css static/css/input.css
COPY templates/ templates/
COPY apps/ apps/
RUN npx tailwindcss -i static/css/input.css -o static/css/output.css --minify

# ---------------------------------------------------------------------------
# Stage 4: Production — slim, secure, ready to deploy
# ---------------------------------------------------------------------------
FROM base AS production

ARG GIT_SHA
ENV GIT_SHA=${GIT_SHA}

COPY requirements/base.txt requirements/base.txt
COPY requirements/production.txt requirements/production.txt
RUN pip install -r requirements/production.txt

# Remove build tools to reduce image size
RUN apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Copy Tailwind-built CSS from builder stage
COPY --from=tailwind-builder /app/static/css/output.css static/css/output.css

# Create non-root user
RUN addgroup --system django && adduser --system --ingroup django django

# Collect static files (must fail loudly — no || true)
ENV DJANGO_SETTINGS_MODULE=baky.settings.production
RUN SECRET_KEY=build-placeholder ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite:///tmp/throwaway.db \
    FIELD_ENCRYPTION_KEY=dGhpcy1pcy1hLWJ1aWxkLXRpbWUtcGxhY2Vob2xkZXI= \
    CSRF_TRUSTED_ORIGINS=https://localhost \
    AWS_ACCESS_KEY_ID=build-placeholder \
    AWS_SECRET_ACCESS_KEY=build-placeholder \
    AWS_STORAGE_BUCKET_NAME=build-placeholder \
    AWS_S3_ENDPOINT_URL=https://localhost \
    RESEND_API_KEY=build-placeholder \
    SITE_URL=https://localhost \
    python manage.py collectstatic --noinput

USER django

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f --connect-timeout 2 --max-time 4 http://localhost:8000/health/ || exit 1

EXPOSE 8000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "baky.wsgi:application"]
