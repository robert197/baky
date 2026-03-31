---
name: new-view
description: Create a new Django view with HTMX patterns, template, URL, and tests. Follows BAKY conventions for owner dashboard, inspector app, or public pages.
user-invokable: true
argument-hint: "<app_name> <view_name> [--type=public|dashboard|inspector]"
---

# Create a New View

## Input
Parse `$ARGUMENTS` for: app name, view name, view type (public/dashboard/inspector).
Default type is `dashboard` if not specified.

## Step 1: Determine Layout

| Type | Base Template | Auth Required | URL Prefix |
|------|--------------|---------------|------------|
| public | `public/base_public.html` | No | `/` (German slugs) |
| dashboard | `dashboard/base_dashboard.html` | Yes (Owner) | `/dashboard/` |
| inspector | `inspector/base_inspector.html` | Yes (Inspector) | `/inspector/` |

## Step 2: Create the View

Add to `apps/<app_name>/views.py`:

**For simple pages (public, detail views):**
```python
def view_name(request):
    context = {}
    return render(request, "<app_name>/view_name.html", context)
```

**For authenticated views:**
```python
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import owner_required  # or inspector_required

@login_required
@owner_required
def view_name(request):
    # Scope to current user's data
    apartments = request.user.apartments.all()
    context = {"apartments": apartments}
    return render(request, "<app_name>/view_name.html", context)
```

**For HTMX partial responses:**
```python
def view_name(request):
    context = {}
    if request.headers.get("HX-Request"):
        return render(request, "<app_name>/_view_name_partial.html", context)
    return render(request, "<app_name>/view_name.html", context)
```

## Step 3: Create Template

Create `templates/<app_name>/view_name.html`:

```html
{% extends "dashboard/base_dashboard.html" %}

{% block title %}Page Title{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <h1 class="text-2xl font-bold text-slate-800 mb-6">Page Title</h1>
  <!-- Content here -->
</div>
{% endblock %}
```

For HTMX partials, also create `templates/<app_name>/_view_name_partial.html`.

**Follow design principles from CLAUDE.md:**
- Mobile-first Tailwind classes
- Use color tokens: slate-800 headings, amber-500 accents, emerald/amber/rose for status
- Large tap targets for inspector views (min 44px)
- Progressive disclosure: essentials first, details on demand

## Step 4: Add URL

Add to `apps/<app_name>/urls.py`:

```python
path("view-name/", views.view_name, name="view_name"),
```

## Step 5: Write Tests

```python
@pytest.mark.django_db
class TestViewName:
    def test_get(self, client):
        # For authenticated views: create user, log in
        response = client.get(reverse("<app_name>:view_name"))
        assert response.status_code == 200

    def test_requires_auth(self, client):
        response = client.get(reverse("<app_name>:view_name"))
        assert response.status_code == 302  # Redirect to login
```

## Step 6: Verify

```bash
make test ARGS="-k test_view_name"
make lint
```
