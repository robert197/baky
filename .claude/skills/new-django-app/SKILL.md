---
name: new-django-app
description: Scaffold a new Django app within the BAKY project with proper structure, admin, tests, and registration.
user-invokable: true
argument-hint: "<app_name>"
---

# Create a New Django App

## Prerequisites
- Docker must be running (`make up`)
- App name provided in `$ARGUMENTS`

If no app name provided, ask the user.

## Step 1: Create the App

```bash
make manage CMD="startapp $APP_NAME"
mv $APP_NAME apps/$APP_NAME
```

## Step 2: Set Up the App Structure

Create/update these files in `apps/$APP_NAME/`:

### `apps.py`
```python
from django.apps import AppConfig

class ${AppNameCamel}Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.${app_name}"
    verbose_name = "${App Name}"
```

### `models.py`
```python
from django.db import models
from apps.core.models import TimeStampedModel


# Models go here. Inherit from TimeStampedModel for created_at/updated_at.
```

### `admin.py`
```python
from django.contrib import admin

# Register models here with @admin.register(Model)
```

### `urls.py`
```python
from django.urls import path

app_name = "${app_name}"

urlpatterns = []
```

### `views.py` (keep default)

### Create directories:
```
apps/$APP_NAME/
├── templates/$APP_NAME/    # App-specific templates
├── templatetags/           # Custom template tags (if needed)
│   └── __init__.py
└── migrations/
    └── __init__.py
```

### Test structure:
```
tests/$APP_NAME/
├── __init__.py
├── test_models.py
├── test_views.py
└── test_admin.py
```

## Step 3: Register the App

Add `"apps.${app_name}"` to `INSTALLED_APPS` in `baky/settings/base.py`.

Add URL include to `baky/urls.py`:
```python
path("${url_prefix}/", include("apps.${app_name}.urls")),
```

## Step 4: Verify

```bash
make manage CMD="check"
make test
```
