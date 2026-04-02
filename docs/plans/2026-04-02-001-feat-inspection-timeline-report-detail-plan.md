---
title: "feat: Inspection timeline and report detail view"
type: feat
status: completed
date: 2026-04-02
issue: 17
---

# Inspection Timeline and Report Detail View

## Overview

Build the inspection history timeline and detailed report view for property owners. The apartment detail page currently shows the last 5 completed inspections; this feature replaces that with a full, filterable timeline with HTMX-expandable summaries. A new report detail view renders live from the database (inspection items, photos, notes) instead of the stored HTML blob, enabling interactive features like an Alpine.js photo lightbox.

## Design Decisions

1. **Timeline scope**: Show only `COMPLETED` inspections (consistent with current behavior). Scheduled/cancelled inspections are not actionable for owners and would require additional badge types.
2. **Pagination**: HTMX "load more" button, 10 inspections per page. Simple, mobile-friendly, no complex pagination UI.
3. **HTMX expansion**: Independent (not accordion) — owners can compare multiple inspections side by side.
4. **Summary content**: Overall rating, flagged item count, photo count, truncated general notes, link to full report.
5. **Report rendering**: Live from database (Inspection + Items + Photos), not from `html_content` blob. This enables the photo lightbox and interactive features. The stored HTML continues for emails/PDF.
6. **Filters**: URL query parameters (`?rating=urgent&from=2026-01-01&to=2026-03-31`) for bookmarkability. HTMX submits filters without full page reload.
7. **Photo lightbox**: Pure Alpine.js implementation with swipe navigation, keyboard support (Escape, arrow keys). Use the existing `/reports/photos/<id>/` proxy endpoint for fresh signed URLs.
8. **Navigation**: Keep timeline scoped under apartment detail (`/dashboard/apartments/<pk>/inspections/`). Don't activate top-level "Inspektionen"/"Berichte" nav items yet — that's a future information architecture change.

## System-Wide Impact

- **Interaction graph**: New views are read-only — no callbacks, middleware, or state mutations beyond the standard `@owner_required` decorator.
- **Error propagation**: Signed URL generation in `Photo.get_file_url()` returns `None` on failure; templates handle this gracefully.
- **State lifecycle risks**: None — all views are read-only.
- **API surface parity**: The new report detail view supplements (does not replace) the existing `dashboard:report_detail` view which renders stored HTML. Both should be accessible — the new view adds interactivity.

## Acceptance Criteria

- [ ] Timeline shows all completed inspections chronologically with pagination
- [ ] Filter by date range and rating works via URL query params
- [ ] Expanding a timeline entry shows inline summary via HTMX
- [ ] Full report detail view shows all checklist items grouped by category
- [ ] Per-item results with notes, severity, and photo thumbnails
- [ ] Photo lightbox works on mobile (swipe, close, keyboard on desktop)
- [ ] Urgent/flagged items visually highlighted with rose background
- [ ] Inspector contact info shown (with fallback when missing)
- [ ] All views enforce owner-only access (cross-owner returns 404)
- [ ] Empty states for: no inspections, no items, no photos, filter returns zero results
- [ ] Existing `_status_badge.html` component used for all rating badges
- [ ] Back navigation returns to apartment detail (not dashboard index)

## Implementation Tasks

### Task 1: Inspection timeline view and URL

**Files:**
- `apps/dashboard/views.py` — add `inspection_timeline` view
- `apps/dashboard/urls.py` — add URL pattern
- `templates/dashboard/inspection_timeline.html` — timeline page
- `templates/dashboard/_inspection_timeline_item.html` — single item partial
- `tests/dashboard/test_inspection_views.py` — new test file

**Tests (write first):**

```python
# tests/dashboard/test_inspection_views.py
import pytest
from django.test import Client
from django.urls import reverse

from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectorFactory,
    OwnerFactory,
    ReportFactory,
)


@pytest.mark.django_db
class TestInspectionTimeline:
    def test_timeline_shows_completed_inspections(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(apartment=apt, status="completed")
        InspectionFactory(apartment=apt, status="completed")
        InspectionFactory(apartment=apt, status="scheduled")  # not shown
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 2

    def test_timeline_empty_state(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert "Noch keine Inspektionen" in resp.content.decode()

    def test_timeline_owner_scoping(self):
        owner = OwnerFactory()
        other = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        client = Client()
        client.force_login(other)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 404

    def test_timeline_unauthenticated_redirect(self):
        apt = ApartmentFactory()
        client = Client()
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 302

    def test_timeline_inspector_denied(self):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        client = Client()
        client.force_login(inspector)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 302  # redirected by @owner_required

    def test_timeline_filter_by_rating(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        InspectionFactory(apartment=apt, status="completed", overall_rating="ok")
        InspectionFactory(apartment=apt, status="completed", overall_rating="urgent")
        client = Client()
        client.force_login(owner)
        resp = client.get(
            reverse("dashboard:inspection_timeline", args=[apt.pk]),
            {"rating": "urgent"},
        )
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 1

    def test_timeline_filter_by_date_range(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        # Create inspections at different dates — use completed_at
        from django.utils import timezone
        import datetime
        old = InspectionFactory(
            apartment=apt, status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=60),
        )
        recent = InspectionFactory(
            apartment=apt, status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=5),
        )
        client = Client()
        client.force_login(owner)
        from_date = (timezone.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        resp = client.get(
            reverse("dashboard:inspection_timeline", args=[apt.pk]),
            {"from": from_date},
        )
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 1

    def test_timeline_pagination_load_more(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        for _ in range(15):
            InspectionFactory(apartment=apt, status="completed")
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert resp.content.decode().count("inspection-item") == 10
        assert "Mehr laden" in resp.content.decode()
```

**Implementation:**

View (`apps/dashboard/views.py`):
```python
@owner_required
def inspection_timeline(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    inspections = (
        apartment.inspections.filter(status=Inspection.Status.COMPLETED)
        .annotate(
            has_report=Exists(
                Report.objects.filter(
                    inspection=OuterRef("pk"),
                    status=Report.Status.COMPLETED,
                ).exclude(html_content="")
            ),
            flagged_count=Count("items", filter=Q(items__result=InspectionItem.Result.FLAGGED)),
            photo_count=Count("photos"),
        )
        .select_related("inspector", "report")
        .order_by("-completed_at")
    )

    # Filters
    rating = request.GET.get("rating")
    if rating in ("ok", "attention", "urgent"):
        inspections = inspections.filter(overall_rating=rating)
    date_from = request.GET.get("from")
    if date_from:
        inspections = inspections.filter(completed_at__date__gte=date_from)
    date_to = request.GET.get("to")
    if date_to:
        inspections = inspections.filter(completed_at__date__lte=date_to)

    # Pagination
    page = int(request.GET.get("page", 1))
    per_page = 10
    total = inspections.count()
    inspections = inspections[(page - 1) * per_page : page * per_page]
    has_more = page * per_page < total

    context = {
        "apartment": apartment,
        "inspections": inspections,
        "has_more": has_more,
        "next_page": page + 1,
        "active": "apartments",
        "current_rating": rating or "",
        "current_from": date_from or "",
        "current_to": date_to or "",
    }

    # HTMX "load more" returns partial
    if request.headers.get("HX-Request") and request.GET.get("page"):
        return render(request, "dashboard/_inspection_timeline_items.html", context)

    return render(request, "dashboard/inspection_timeline.html", context)
```

URL (`apps/dashboard/urls.py`):
```python
path("apartments/<int:pk>/inspections/", views.inspection_timeline, name="inspection_timeline"),
```

**Verify:** `make test ARGS="-k TestInspectionTimeline"`

---

### Task 2: HTMX inspection summary expansion

**Files:**
- `apps/dashboard/views.py` — add `inspection_summary` view
- `apps/dashboard/urls.py` — add URL pattern
- `templates/dashboard/_inspection_summary.html` — summary fragment
- `tests/dashboard/test_inspection_views.py` — add tests

**Tests (write first):**

```python
@pytest.mark.django_db
class TestInspectionSummary:
    def test_summary_returns_html_fragment(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", general_notes="Alles in Ordnung")
        client = Client()
        client.force_login(owner)
        resp = client.get(
            reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]),
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert "Alles in Ordnung" in resp.content.decode()

    def test_summary_owner_scoping(self):
        owner = OwnerFactory()
        other = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        client = Client()
        client.force_login(other)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        assert resp.status_code == 404

    def test_summary_shows_flagged_count(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        from tests.factories import InspectionItemFactory
        InspectionItemFactory(inspection=insp, result="flagged")
        InspectionItemFactory(inspection=insp, result="flagged")
        InspectionItemFactory(inspection=insp, result="ok")
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "2" in content  # 2 flagged items

    def test_summary_without_report(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        # No report created
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        # Should NOT crash (OneToOne reverse access pitfall)
```

**Implementation:**

View:
```python
@owner_required
def inspection_summary(request, pk, inspection_pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    inspection = get_object_or_404(
        apartment.inspections.filter(status=Inspection.Status.COMPLETED)
        .annotate(
            has_report=Exists(
                Report.objects.filter(
                    inspection=OuterRef("pk"),
                    status=Report.Status.COMPLETED,
                ).exclude(html_content="")
            ),
            flagged_count=Count("items", filter=Q(items__result=InspectionItem.Result.FLAGGED)),
            photo_count=Count("photos"),
        )
        .select_related("inspector", "report"),
        pk=inspection_pk,
    )
    return render(request, "dashboard/_inspection_summary.html", {
        "apartment": apartment,
        "inspection": inspection,
    })
```

URL:
```python
path("apartments/<int:pk>/inspections/<int:inspection_pk>/summary/", views.inspection_summary, name="inspection_summary"),
```

Template (`_inspection_summary.html`): Renders rating badge, flagged/photo counts, truncated general notes, "Bericht ansehen" link if `has_report`.

**Verify:** `make test ARGS="-k TestInspectionSummary"`

---

### Task 3: Report detail view (live from database)

**Files:**
- `apps/dashboard/views.py` — add `inspection_report_detail` view
- `apps/dashboard/urls.py` — add URL pattern
- `templates/dashboard/report_detail.html` — new template (replaces reliance on stored HTML)
- `tests/dashboard/test_inspection_views.py` — add tests

**Tests (write first):**

```python
@pytest.mark.django_db
class TestInspectionReportDetail:
    def test_report_detail_shows_checklist_items(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        from tests.factories import InspectionItemFactory
        InspectionItemFactory(inspection=insp, category="Küche", result="ok")
        InspectionItemFactory(inspection=insp, category="Küche", result="flagged", severity="high")
        InspectionItemFactory(inspection=insp, category="Bad", result="ok")
        report = ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Küche" in content
        assert "Bad" in content

    def test_report_detail_groups_items_by_category(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        from tests.factories import InspectionItemFactory
        InspectionItemFactory(inspection=insp, category="Küche", checklist_label="Herd")
        InspectionItemFactory(inspection=insp, category="Küche", checklist_label="Spüle")
        InspectionItemFactory(inspection=insp, category="Wohnzimmer", checklist_label="Sofa")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        # Categories appear as section headers
        assert "Küche" in content
        assert "Wohnzimmer" in content

    def test_report_detail_shows_photos(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        from tests.factories import InspectionItemFactory, PhotoFactory
        item = InspectionItemFactory(inspection=insp, result="flagged")
        PhotoFactory(inspection=insp, inspection_item=item, caption="Wasserschaden")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        assert "Wasserschaden" in resp.content.decode()

    def test_report_detail_without_report_shows_items_anyway(self):
        """Inspection without generated report should still show checklist results."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        from tests.factories import InspectionItemFactory
        InspectionItemFactory(inspection=insp, result="ok")
        # No report
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200

    def test_report_detail_owner_scoping(self):
        owner = OwnerFactory()
        other = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(other)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 404

    def test_report_detail_unauthenticated(self):
        apt = ApartmentFactory()
        insp = InspectionFactory(apartment=apt, status="completed")
        client = Client()
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 302

    def test_report_detail_highlights_urgent_items(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed", overall_rating="urgent")
        from tests.factories import InspectionItemFactory
        InspectionItemFactory(inspection=insp, result="flagged", severity="urgent")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "bg-rose-50" in content  # urgent highlight

    def test_report_detail_inspector_contact(self):
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(first_name="Max", last_name="Müller", phone="+43 660 1234567")
        insp = InspectionFactory(apartment=apt, status="completed", inspector=inspector)
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "Max Müller" in content
        assert "+43 660 1234567" in content

    def test_report_detail_inspector_no_contact(self):
        """Inspector without phone/email shows fallback message."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(phone="", email="")
        insp = InspectionFactory(apartment=apt, status="completed", inspector=inspector)
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        content = resp.content.decode()
        assert "BAKY" in content  # fallback contact

    def test_report_detail_empty_checklist(self):
        """Completed inspection with no items shows appropriate message."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        insp = InspectionFactory(apartment=apt, status="completed")
        ReportFactory(inspection=insp)
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
```

**Implementation:**

View:
```python
@owner_required
def inspection_report_detail(request, pk, inspection_pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    inspection = get_object_or_404(
        apartment.inspections.filter(status=Inspection.Status.COMPLETED)
        .select_related("inspector"),
        pk=inspection_pk,
    )
    items = (
        inspection.items.all()
        .prefetch_related("photos")
        .order_by("category", "order")
    )
    # Group items by category
    from itertools import groupby
    grouped_items = []
    for category, group in groupby(items, key=lambda i: i.category):
        group_list = list(group)
        flagged_in_group = sum(1 for i in group_list if i.result == InspectionItem.Result.FLAGGED)
        grouped_items.append({
            "category": category,
            "items": group_list,
            "flagged_count": flagged_in_group,
        })

    # General photos (not attached to any item)
    general_photos = inspection.photos.filter(inspection_item__isnull=True)

    # Check report existence safely (OneToOne reverse)
    try:
        report = inspection.report if inspection.report.is_ready else None
    except Report.DoesNotExist:
        report = None

    # Duration
    duration = None
    if inspection.started_at and inspection.completed_at:
        duration = inspection.completed_at - inspection.started_at

    return render(request, "dashboard/report_detail.html", {
        "apartment": apartment,
        "inspection": inspection,
        "grouped_items": grouped_items,
        "general_photos": general_photos,
        "report": report,
        "duration": duration,
        "active": "apartments",
    })
```

URL:
```python
path("apartments/<int:pk>/inspections/<int:inspection_pk>/report/", views.inspection_report_detail, name="inspection_report_detail"),
```

**Verify:** `make test ARGS="-k TestInspectionReportDetail"`

---

### Task 4: Timeline template with filters and HTMX expansion

**Files:**
- `templates/dashboard/inspection_timeline.html` — full page template
- `templates/dashboard/_inspection_timeline_items.html` — items partial (for HTMX load-more)
- `templates/dashboard/_inspection_timeline_item.html` — single item row
- `templates/dashboard/_inspection_summary.html` — expansion fragment

**Implementation notes:**

Timeline page extends `dashboard/base_dashboard.html`. Filter form at top with:
- Rating filter: toggle chips (Alle / OK / Achtung / Dringend)
- Date range: native `<input type="date">` for `from` and `to`
- Filters submit via HTMX `hx-get` with `hx-push-url="true"` targeting the items container

Each timeline item:
- Shows date, inspector name, rating badge (`{% include "components/_status_badge.html" with status=inspection.overall_rating %}`)
- Has `hx-get` to load summary on click, targeting a div below the item
- `aria-expanded` toggled via Alpine.js

Load more button:
- `hx-get="?page={{ next_page }}"` with `hx-target` appending to items list, `hx-swap="beforeend"`

**Verify:** Manual test in browser (run `make up`), plus `make test ARGS="-k TestInspectionTimeline"`

---

### Task 5: Report detail template with photo lightbox

**Files:**
- `templates/dashboard/report_detail.html` — full report page (new template, different from existing `reports/report_detail.html`)
- `templates/dashboard/_photo_lightbox.html` — Alpine.js lightbox component

**Implementation notes:**

Report detail page extends `dashboard/base_dashboard.html`. Sections:
1. **Header**: Inspection date, overall rating badge, inspector name, duration
2. **Checklist results**: Grouped by category. Each category collapsible. Flagged items have `bg-rose-50` background. Each item shows: label, result badge, severity if flagged, notes, photo thumbnails
3. **General notes**: Inspector's `general_notes` field
4. **Photo gallery**: Grid of all photos (thumbnails). Click opens lightbox.
5. **Inspector contact**: Name, phone (clickable `tel:` link), email (clickable `mailto:` link). Fallback: "Fur Ruckfragen kontaktieren Sie bitte BAKY"
6. **Back link**: Links to `dashboard:inspection_timeline` (not dashboard index)

Photo lightbox (Alpine.js):
```html
<div x-data="photoLightbox()" x-show="isOpen" x-cloak ...>
```
- Opens on photo click with photo array and current index
- Arrow keys / swipe to navigate
- Escape to close
- Loading spinner while image loads
- Uses `/reports/photos/<id>/` proxy endpoint for full-size URLs (fresh signed URLs)
- Touch events for swipe (use `@touchstart`, `@touchend` to calculate swipe direction)

**Verify:** Manual browser test on mobile viewport (375px), `make test`

---

### Task 6: Update apartment detail to link to timeline

**Files:**
- `templates/dashboard/apartment_detail.html` — update recent inspections section
- `apps/dashboard/views.py` — no changes needed (existing view already queries 5 recent inspections)

**Implementation:**

Replace the "Letzte Inspektionen" section heading with a link: "Letzte Inspektionen" + "Alle anzeigen" link to `dashboard:inspection_timeline`. Keep showing the last 5 as-is but use `_status_badge.html` component instead of inline badge markup. Add link to `dashboard:inspection_report_detail` for each inspection.

**Tests (add to existing test file):**

```python
def test_apartment_detail_links_to_timeline(self):
    owner = OwnerFactory()
    apt = ApartmentFactory(owner=owner)
    InspectionFactory(apartment=apt, status="completed")
    client = Client()
    client.force_login(owner)
    resp = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
    assert reverse("dashboard:inspection_timeline", args=[apt.pk]) in resp.content.decode()
```

**Verify:** `make test ARGS="-k test_apartment_detail"`

---

### Task 7: Integration test — full flow

**Files:**
- `tests/dashboard/test_integration.py` — add integration test

**Test:**

```python
@pytest.mark.django_db
class TestInspectionReportFlow:
    def test_apartment_to_timeline_to_report(self):
        """Full flow: apartment detail -> timeline -> report detail."""
        owner = OwnerFactory()
        apt = ApartmentFactory(owner=owner)
        inspector = InspectorFactory(first_name="Anna", last_name="Schmidt")
        insp = InspectionFactory(
            apartment=apt, inspector=inspector,
            status="completed", overall_rating="attention",
        )
        InspectionItemFactory(inspection=insp, category="Küche", result="ok")
        InspectionItemFactory(inspection=insp, category="Küche", result="flagged", severity="medium")
        PhotoFactory(inspection=insp, caption="Küchenregal")
        ReportFactory(inspection=insp)

        client = Client()
        client.force_login(owner)

        # Step 1: Apartment detail
        resp = client.get(reverse("dashboard:apartment_detail", args=[apt.pk]))
        assert resp.status_code == 200

        # Step 2: Timeline
        resp = client.get(reverse("dashboard:inspection_timeline", args=[apt.pk]))
        assert resp.status_code == 200
        assert "Anna Schmidt" in resp.content.decode()

        # Step 3: Summary expansion
        resp = client.get(reverse("dashboard:inspection_summary", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200

        # Step 4: Report detail
        resp = client.get(reverse("dashboard:inspection_report_detail", args=[apt.pk, insp.pk]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Küche" in content
        assert "Küchenregal" in content
        assert "Anna Schmidt" in content
```

**Verify:** `make test ARGS="-k TestInspectionReportFlow"`

## Dependencies & Risks

- **OneToOne reverse access**: Must use `has_report` annotation or try/except, never direct `inspection.report` in templates. See `docs/solutions/runtime-errors/django-reverse-onetoone-relatedobjectdoesnotexist-in-templates.md`.
- **Template comments**: Must use `{# #}`, never HTML comments with template tags. See `docs/solutions/runtime-errors/django-template-tags-in-html-comments-recursion.md`.
- **Photo lightbox**: Pure Alpine.js — no external library dependency. Keep it simple: navigate, zoom (CSS transform), close.
- **Signed URL expiry**: Use proxy endpoint for lightbox full-size images so URLs are always fresh.

## Sources & References

- Existing `apartment_detail` view: `apps/dashboard/views.py:43-69`
- Existing report detail: `apps/reports/views.py:1-37`, `templates/reports/report_detail.html`
- Status badge component: `templates/components/_status_badge.html`
- Photo model with signed URLs: `apps/inspections/models.py:180-225`, `baky/storage.py:99-116`
- OneToOne solution: `docs/solutions/runtime-errors/django-reverse-onetoone-relatedobjectdoesnotexist-in-templates.md`
- Related issue: #17
- Roadmap: #44
