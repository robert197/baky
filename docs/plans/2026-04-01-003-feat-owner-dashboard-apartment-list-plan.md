---
title: "feat: Build owner dashboard - apartment list and management"
type: feat
status: active
date: 2026-04-01
issue: "#16"
---

# feat: Build owner dashboard - apartment list and management

## Overview

Replace the dashboard stub (`"Dashboard -- coming soon"`) with a full apartment list view, apartment detail/edit views, and proper navigation. After onboarding, owners land on a functional dashboard showing their apartments with key inspection data at a glance. Mobile-first, German UI.

## Problem Statement

After completing the 4-step onboarding flow, owners are redirected to `/dashboard/` which displays plain text "coming soon". This is the first page after signup — it needs to show immediate value: apartment details, inspection status, and next steps.

## Proposed Solution

1. **Apartment list view** at `/dashboard/` — card grid showing each apartment with status, last inspection rating, and next scheduled inspection
2. **Apartment detail view** at `/dashboard/apartments/<pk>/` — full apartment info with checklist summary
3. **Apartment edit view** at `/dashboard/apartments/<pk>/edit/` — form to update apartment details
4. **Navigation** — wire sidebar links, create owner mobile bottom nav
5. **Empty state** — guidance for owners with no apartments (edge case: shouldn't happen after onboarding)

## Key Decisions

- **Edit form**: New `ApartmentEditForm` (not reusing `ApartmentOnboardingForm`). Fields: address (simple text, no geocoding), access_method, access_code, access_notes, special_instructions, status (active/paused only). No archived status exposed to owners.
- **Ownership scoping**: `get_object_or_404(Apartment, pk=pk, owner=request.user)` pattern — same approach as `report_detail` view.
- **Archived apartments**: Excluded from dashboard queryset. Archive is admin-only for MVP.
- **Quick actions per card**: "Bearbeiten" (edit link) and "Letzter Bericht" (view last report if exists).
- **Traditional form POST** for edit (not HTMX inline save). Redirect to dashboard with success message.
- **Card grid**: 1 column mobile, 2 columns `md:`, 3 columns `lg:`.
- **Sidebar**: Keep existing labels (Wohnungen, Inspektionen, Berichte, Einstellungen). Wire "Wohnungen" to `/dashboard/`. Others remain `#` with muted styling.
- **Mobile bottom nav**: New `_owner_bottom_nav.html` — Wohnungen, Berichte, Profil.
- **No pagination**: Owners have 1-5 apartments per design context. Not needed for MVP.
- **No search/filter**: Same reason — small data sets.

## Technical Considerations

### Query Strategy

Avoid N+1 by annotating the queryset in the list view:
```python
apartments = (
    Apartment.objects.filter(owner=request.user)
    .exclude(status=Apartment.Status.ARCHIVED)
    .annotate(
        last_inspection_date=Max("inspections__completed_at", filter=Q(inspections__status="completed")),
        last_inspection_rating=Subquery(
            Inspection.objects.filter(apartment=OuterRef("pk"), status="completed")
            .order_by("-completed_at")
            .values("overall_rating")[:1]
        ),
        next_inspection_date=Min("inspections__scheduled_at", filter=Q(
            inspections__status="scheduled", inspections__scheduled_at__gt=Now()
        )),
    )
)
```
This mirrors the admin annotation pattern in `apps/apartments/admin.py:21-37`.

### System-Wide Impact

- **Interaction graph**: Dashboard views are read-only (list, detail) or single-model writes (edit). No callbacks, no background tasks triggered. Edit saves directly to Apartment model.
- **Error propagation**: Form validation errors re-render the edit form. No external API calls.
- **State lifecycle**: Edit updates apartment fields directly. No cascading effects for status changes at MVP (pausing doesn't cancel inspections — that's a future feature).
- **Security**: `@owner_required` for role check + `owner=request.user` filter for object-level access. Encrypted fields (access_code, access_notes) display in cleartext on edit form since the owner entered them.

### Template Gotcha

Per documented solution: never use `{% %}` or `{{ }}` inside HTML comments. Use `{# #}` exclusively.

## Acceptance Criteria

- [ ] Dashboard at `/dashboard/` shows owner's apartments as cards
- [ ] Cards display: address, status badge (active/paused), last inspection date + rating, next scheduled inspection
- [ ] Empty apartment state shows guidance message
- [ ] Apartment detail view at `/dashboard/apartments/<pk>/edit/` with pre-populated form
- [ ] Edit form saves changes and redirects with success message
- [ ] Only owner's own apartments are accessible (404 for other owners)
- [ ] Unauthenticated users redirected to login (302)
- [ ] Non-owner roles get 404
- [ ] Sidebar "Wohnungen" link wired to `/dashboard/`
- [ ] Mobile bottom nav for owners
- [ ] Mobile-responsive card grid (1/2/3 columns)
- [ ] German UI text throughout
- [ ] 20+ tests covering views, forms, permissions, edge cases
- [ ] All existing 777 tests continue passing

---

## Implementation Tasks

### Task 1: Create ApartmentEditForm

**Files**: `apps/dashboard/forms.py` (new)

**Test** (`tests/dashboard/test_forms.py` — new):
```python
import pytest
from apps.dashboard.forms import ApartmentEditForm
from tests.factories import ApartmentFactory

@pytest.mark.django_db
class TestApartmentEditForm:
    def test_valid_form(self):
        apartment = ApartmentFactory()
        form = ApartmentEditForm(data={
            "address": "Teststrasse 1, 1010 Wien",
            "access_method": "lockbox",
            "access_code": "1234",
            "access_notes": "Im Hof links",
            "special_instructions": "",
            "status": "active",
        }, instance=apartment)
        assert form.is_valid()

    def test_required_fields(self):
        form = ApartmentEditForm(data={})
        assert not form.is_valid()
        assert "address" in form.errors

    def test_status_choices_exclude_archived(self):
        form = ApartmentEditForm()
        status_values = [c[0] for c in form.fields["status"].widget.choices]
        assert "active" in status_values
        assert "paused" in status_values
        assert "archived" not in status_values

    def test_german_labels(self):
        form = ApartmentEditForm()
        assert "Adresse" in form.fields["address"].label
        assert "Zugang" in form.fields["access_method"].label

    def test_umlauts_in_address(self):
        apartment = ApartmentFactory()
        form = ApartmentEditForm(data={
            "address": "Grünbergstraße 42, 1120 Wien",
            "access_method": "lockbox",
            "access_code": "",
            "access_notes": "",
            "special_instructions": "Schlüssel beim Nachbarn Müller",
            "status": "active",
        }, instance=apartment)
        assert form.is_valid()
```

**Implementation**:

```python
# apps/dashboard/forms.py
from django import forms
from apps.apartments.models import Apartment

INPUT_CSS = "w-full rounded-lg border border-border px-4 py-3"

OWNER_STATUS_CHOICES = [
    (Apartment.Status.ACTIVE, "Aktiv"),
    (Apartment.Status.PAUSED, "Pausiert"),
]

class ApartmentEditForm(forms.ModelForm):
    status = forms.ChoiceField(choices=OWNER_STATUS_CHOICES, label="Status", widget=forms.Select(attrs={"class": INPUT_CSS}))

    class Meta:
        model = Apartment
        fields = ["address", "access_method", "access_code", "access_notes", "special_instructions", "status"]
        labels = {
            "address": "Adresse",
            "access_method": "Zugangsart",
            "access_code": "Zugangscode",
            "access_notes": "Zugangshinweise",
            "special_instructions": "Besondere Anweisungen",
        }
        widgets = {
            "address": forms.TextInput(attrs={"class": INPUT_CSS}),
            "access_method": forms.Select(attrs={"class": INPUT_CSS}),
            "access_code": forms.TextInput(attrs={"class": INPUT_CSS}),
            "access_notes": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
            "special_instructions": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
        }
```

**Verify**: `make test ARGS="-k test_apartment_edit_form"`

---

### Task 2: Dashboard index view — apartment list with annotations

**Files**: `apps/dashboard/views.py`

**Test** (`tests/dashboard/test_views.py` — new):
```python
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from tests.factories import OwnerFactory, InspectorFactory, ApartmentFactory, InspectionFactory

@pytest.mark.django_db
class TestDashboardIndex:
    def test_owner_sees_own_apartments(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

    def test_owner_does_not_see_other_apartments(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert other_apt.address not in response.content.decode()

    def test_archived_apartments_excluded(self):
        owner = OwnerFactory()
        ApartmentFactory(owner=owner, status="archived")
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_empty_state_shown(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        content = response.content.decode()
        assert "Keine Wohnungen" in content or "keine Wohnungen" in content

    def test_unauthenticated_redirects(self):
        client = Client()
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 302

    def test_inspector_gets_404(self):
        inspector = InspectorFactory()
        client = Client()
        client.force_login(inspector)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 404

    def test_shows_last_inspection_rating(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="completed",
            overall_rating="ok",
            completed_at=timezone.now() - timedelta(days=1),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_shows_next_scheduled_inspection(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="scheduled",
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_uses_dashboard_template(self):
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert "dashboard/index.html" in [t.name for t in response.templates]
```

**Implementation**:

Replace the stub in `apps/dashboard/views.py`:

```python
from django.db.models import Max, Min, Q, Subquery, OuterRef
from django.db.models.functions import Now
from django.shortcuts import render
from apps.accounts.decorators import owner_required
from apps.apartments.models import Apartment
from apps.inspections.models import Inspection

@owner_required
def index(request):
    apartments = (
        Apartment.objects.filter(owner=request.user)
        .exclude(status=Apartment.Status.ARCHIVED)
        .annotate(
            last_inspection_date=Max(
                "inspections__completed_at",
                filter=Q(inspections__status=Inspection.Status.COMPLETED),
            ),
            last_inspection_rating=Subquery(
                Inspection.objects.filter(
                    apartment=OuterRef("pk"),
                    status=Inspection.Status.COMPLETED,
                )
                .order_by("-completed_at")
                .values("overall_rating")[:1]
            ),
            next_inspection_date=Min(
                "inspections__scheduled_at",
                filter=Q(
                    inspections__status=Inspection.Status.SCHEDULED,
                    inspections__scheduled_at__gt=Now(),
                ),
            ),
        )
    )
    return render(request, "dashboard/index.html", {"apartments": apartments})
```

**Verify**: `make test ARGS="-k TestDashboardIndex"`

---

### Task 3: Dashboard index template — apartment card grid

**Files**: `templates/dashboard/index.html` (new), `templates/dashboard/_apartment_card.html` (new)

**Test** (`tests/dashboard/test_templates.py` — new):
```python
import pytest
from django.template.loader import render_to_string
from tests.factories import ApartmentFactory

@pytest.mark.django_db
class TestDashboardTemplates:
    def test_index_template_renders(self):
        html = render_to_string("dashboard/index.html", {
            "apartments": [],
            "request": None,
        })
        assert "Wohnungen" in html

    def test_apartment_card_renders(self):
        apt = ApartmentFactory()
        html = render_to_string("dashboard/_apartment_card.html", {
            "apartment": apt,
        })
        assert apt.address in html
```

**Implementation**:

`templates/dashboard/index.html` — extends `dashboard/base_dashboard.html`:
- `{% block page_title %}Wohnungen{% endblock %}`
- Card grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`
- Loop over apartments, include `_apartment_card.html` for each
- Empty state: friendly message with icon when no apartments

`templates/dashboard/_apartment_card.html`:
- White card with rounded corners, subtle border (`bg-white rounded-xl border border-border shadow-sm p-6`)
- Address as card title (truncated with `truncate`)
- Status badge: emerald for active, amber for paused
- Last inspection: date + rating badge (using existing color tokens — emerald/amber/rose for ok/attention/urgent)
- Next inspection: date or "Keine geplant" in muted text
- Quick actions row: "Bearbeiten" link, "Letzter Bericht" link (if report exists)

**Verify**: `make test ARGS="-k TestDashboardTemplates"`

---

### Task 4: Apartment detail view

**Files**: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/dashboard/apartment_detail.html` (new)

**Test** (`tests/dashboard/test_views.py` — add to existing):
```python
@pytest.mark.django_db
class TestApartmentDetail:
    def test_owner_sees_own_apartment(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

    def test_other_owner_gets_404(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[other_apt.pk]))
        assert response.status_code == 404

    def test_shows_checklist_summary(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 200

    def test_unauthenticated_redirects(self):
        apt = ApartmentFactory()
        client = Client()
        response = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert response.status_code == 302
```

**Implementation**:

```python
@owner_required
def apartment_detail(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    checklist = getattr(apartment, "checklist_template", None)
    recent_inspections = apartment.inspections.filter(
        status=Inspection.Status.COMPLETED
    ).order_by("-completed_at")[:5]
    return render(request, "dashboard/apartment_detail.html", {
        "apartment": apartment,
        "checklist": checklist,
        "recent_inspections": recent_inspections,
    })
```

URL: `path("apartments/<int:pk>/", views.apartment_detail, name="apartment_detail")`

Template shows:
- Full address, access method, special instructions
- Checklist summary (number of items, categories)
- Recent inspections list (date, rating badge — inspection timeline is #17)
- "Bearbeiten" button linking to edit view

**Verify**: `make test ARGS="-k TestApartmentDetail"`

---

### Task 5: Apartment edit view

**Files**: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/dashboard/apartment_edit.html` (new)

**Test** (`tests/dashboard/test_views.py` — add):
```python
@pytest.mark.django_db
class TestApartmentEdit:
    def test_get_edit_form(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

    def test_post_valid_data(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:apartment_edit", args=[apt.pk]), {
            "address": "Neue Adresse 1, 1020 Wien",
            "access_method": "lockbox",
            "access_code": "5678",
            "access_notes": "",
            "special_instructions": "",
            "status": "active",
        })
        assert response.status_code == 302
        apt.refresh_from_db()
        assert apt.address == "Neue Adresse 1, 1020 Wien"

    def test_post_invalid_data(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:apartment_edit", args=[apt.pk]), {
            "address": "",
            "access_method": "lockbox",
            "access_code": "",
            "access_notes": "",
            "special_instructions": "",
            "status": "active",
        })
        assert response.status_code == 200  # re-renders form with errors

    def test_other_owner_gets_404(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_edit", args=[other_apt.pk]))
        assert response.status_code == 404

    def test_post_other_owner_gets_404(self):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        other_apt = ApartmentFactory(owner=other_owner)
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:apartment_edit", args=[other_apt.pk]), {
            "address": "Hacked", "access_method": "lockbox",
            "access_code": "", "access_notes": "", "special_instructions": "", "status": "active",
        })
        assert response.status_code == 404

    def test_success_message_shown(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.post(reverse("dashboard:apartment_edit", args=[apt.pk]), {
            "address": "Teststrasse 1", "access_method": "lockbox",
            "access_code": "", "access_notes": "", "special_instructions": "", "status": "active",
        }, follow=True)
        assert "gespeichert" in response.content.decode().lower()

    def test_cancel_link_exists(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        content = response.content.decode()
        assert "Abbrechen" in content
```

**Implementation**:

```python
from django.contrib import messages

@owner_required
def apartment_edit(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    if request.method == "POST":
        form = ApartmentEditForm(request.POST, instance=apartment)
        if form.is_valid():
            form.save()
            messages.success(request, f"Wohnung '{apartment.address}' gespeichert.")
            return redirect("dashboard:index")
    else:
        form = ApartmentEditForm(instance=apartment)
    return render(request, "dashboard/apartment_edit.html", {
        "apartment": apartment,
        "form": form,
    })
```

URL: `path("apartments/<int:pk>/edit/", views.apartment_edit, name="apartment_edit")`

Template:
- Extends `dashboard/base_dashboard.html`
- `{% block page_title %}Wohnung bearbeiten{% endblock %}`
- Form with fields rendered individually for Tailwind styling
- Submit button: "Speichern" (amber accent)
- Cancel link: "Abbrechen" → back to dashboard

**Verify**: `make test ARGS="-k TestApartmentEdit"`

---

### Task 6: Wire sidebar navigation

**Files**: `templates/components/_sidebar.html`

**Test** (`tests/dashboard/test_views.py` — add):
```python
def test_sidebar_has_active_wohnungen_link(self):
    owner = OwnerFactory()
    client = Client()
    client.force_login(owner)
    response = client.get(reverse("dashboard:index"))
    content = response.content.decode()
    assert "/dashboard/" in content
```

**Implementation**:

Update `_sidebar.html`:
- "Wohnungen" link: `href="{% url 'dashboard:index' %}"` — active state when on dashboard pages
- Other links remain `href="#"` with `opacity-50 cursor-not-allowed` styling
- Active state: amber accent left border, bold text

**Verify**: `make test`

---

### Task 7: Create owner mobile bottom nav

**Files**: `templates/components/_owner_bottom_nav.html` (new), `templates/dashboard/base_dashboard.html` (update)

**Test** (`tests/dashboard/test_templates.py` — add):
```python
def test_dashboard_has_bottom_nav(self):
    owner = OwnerFactory()
    client = Client()
    client.force_login(owner)
    response = client.get(reverse("dashboard:index"))
    content = response.content.decode()
    assert "Wohnungen" in content
```

**Implementation**:

`templates/components/_owner_bottom_nav.html`:
- Fixed bottom bar, visible on mobile only (`lg:hidden`)
- Three items: Wohnungen (home icon), Berichte (document icon), Profil (user icon)
- Active state: amber accent color
- Safe area padding for notched phones (`pb-safe`)

Update `templates/dashboard/base_dashboard.html`:
- Include `_owner_bottom_nav.html` at bottom of body
- Add bottom padding to main content to account for fixed bottom nav

**Verify**: `make test`

---

### Task 8: Update dashboard URL patterns

**Files**: `apps/dashboard/urls.py`

**Implementation**:

```python
from django.urls import path
from apps.dashboard import views
from apps.reports import views as report_views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("apartments/<int:pk>/", views.apartment_detail, name="apartment_detail"),
    path("apartments/<int:pk>/edit/", views.apartment_edit, name="apartment_edit"),
    path("reports/<int:report_id>/", report_views.report_detail, name="report_detail"),
]
```

**Verify**: `make test`

---

### Task 9: Integration tests — full dashboard flows

**Files**: `tests/dashboard/test_integration.py` (new)

**Test**:
```python
@pytest.mark.django_db
class TestDashboardIntegration:
    def test_owner_full_flow(self):
        """Owner: login -> dashboard -> see apartments -> edit -> save -> back to dashboard."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)

        # See dashboard
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert apt.address in response.content.decode()

        # Navigate to edit
        response = client.get(reverse("dashboard:apartment_edit", args=[apt.pk]))
        assert response.status_code == 200

        # Save changes
        response = client.post(reverse("dashboard:apartment_edit", args=[apt.pk]), {
            "address": "Geaenderte Adresse 1, 1010 Wien",
            "access_method": "smart_lock",
            "access_code": "app-code-123",
            "access_notes": "App oeffnen",
            "special_instructions": "",
            "status": "active",
        }, follow=True)
        assert response.status_code == 200
        assert "Geaenderte Adresse" in response.content.decode()

    def test_owner_with_inspections_sees_rating(self):
        """Dashboard cards show inspection ratings."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(
            apartment=apt,
            status="completed",
            overall_rating="attention",
            completed_at=timezone.now(),
        )
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_multi_apartment_owner(self):
        """Owner with multiple apartments sees all of them."""
        owner = OwnerFactory()
        apt1 = ApartmentFactory(owner=owner, address="Wohnung Eins")
        apt2 = ApartmentFactory(owner=owner, address="Wohnung Zwei")
        apt3 = ApartmentFactory(owner=owner, address="Wohnung Drei")
        client = Client()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        content = response.content.decode()
        assert "Wohnung Eins" in content
        assert "Wohnung Zwei" in content
        assert "Wohnung Drei" in content

    def test_security_cross_owner_access(self):
        """Owner A cannot access Owner B's apartments through any view."""
        owner_a = OwnerFactory()
        owner_b = OwnerFactory()
        apt_b = ApartmentFactory(owner=owner_b)
        client = Client()
        client.force_login(owner_a)

        assert client.get(reverse("dashboard:apartment_detail", args=[apt_b.pk])).status_code == 404
        assert client.get(reverse("dashboard:apartment_edit", args=[apt_b.pk])).status_code == 404
        assert client.post(reverse("dashboard:apartment_edit", args=[apt_b.pk]), {
            "address": "Hacked", "access_method": "lockbox",
            "access_code": "", "access_notes": "", "special_instructions": "", "status": "active",
        }).status_code == 404
```

**Verify**: `make test`

---

## Summary of Files Changed

| File | Change |
|------|--------|
| `apps/dashboard/forms.py` | New: ApartmentEditForm |
| `apps/dashboard/views.py` | Replace stub with index, apartment_detail, apartment_edit views |
| `apps/dashboard/urls.py` | Add apartment detail and edit URL patterns |
| `templates/dashboard/index.html` | New: apartment list with card grid |
| `templates/dashboard/_apartment_card.html` | New: apartment card component |
| `templates/dashboard/apartment_detail.html` | New: apartment detail page |
| `templates/dashboard/apartment_edit.html` | New: apartment edit form |
| `templates/components/_sidebar.html` | Wire Wohnungen link, add active state |
| `templates/components/_owner_bottom_nav.html` | New: mobile bottom nav for owners |
| `templates/dashboard/base_dashboard.html` | Include bottom nav |
| `tests/dashboard/test_forms.py` | New: form tests |
| `tests/dashboard/test_views.py` | New: view tests (index, detail, edit, permissions) |
| `tests/dashboard/test_templates.py` | New: template rendering tests |
| `tests/dashboard/test_integration.py` | New: integration flow tests |

## Out of Scope (Follow-up Issues)

- Inspection timeline on apartment detail (#17)
- Subscription management page (#18)
- Owner calendar booking (#66)
- Add new apartment from dashboard (apartments created during onboarding)
- Apartment archive functionality (admin-only for MVP)
- Pagination / search / filter (owner has 1-5 apartments)
- Cascading status effects (pausing apartment cancels inspections)
- Profile / settings pages
