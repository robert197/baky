---
title: Dockerfile collectstatic requires ALL production env vars as placeholders
category: build-errors
severity: high
date: 2026-04-02
issue: "#41"
---

## Problem

Docker production image build fails silently at `collectstatic` step because
`production.py` imports require env vars that aren't available at build time.

The original Dockerfile used `2>/dev/null || true` to suppress errors, which
hid the fact that `collectstatic` never actually ran. The production site
would have deployed with no static files (no CSS, no JS).

## Root Cause

Django's `collectstatic` command imports the full settings module, which in
`production.py` includes:
- `FIELD_ENCRYPTION_KEY` — must be a valid Fernet key (base64-encoded 32 bytes)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, etc.
- `RESEND_API_KEY`, `SITE_URL`, `CSRF_TRUSTED_ORIGINS`

All of these raise `ImproperlyConfigured` if not set, and `FIELD_ENCRYPTION_KEY`
specifically validates that the value is a valid Fernet key at import time
(via `encrypted_model_fields`).

## Solution

1. **Remove `|| true`** — collectstatic must fail loudly so broken builds are caught.
2. **Provide ALL required env vars as build-time placeholders** in the `RUN` command.
3. **Use a valid Fernet key** for `FIELD_ENCRYPTION_KEY` (base64-encoded), not just any string.
4. **Use `sqlite:///tmp/throwaway.db`** for `DATABASE_URL` since collectstatic doesn't need a real DB.

```dockerfile
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
```

## Prevention

- Never use `|| true` on build commands that produce critical output.
- When adding new required env vars to production settings, also add them as
  build-time placeholders in the Dockerfile `collectstatic` step.
- Test the production Docker build in CI (`docker build --target production`).
