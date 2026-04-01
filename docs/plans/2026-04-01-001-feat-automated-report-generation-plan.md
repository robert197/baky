---
title: "feat(reports): Automated report generation from inspection data"
type: feat
status: completed
date: 2026-04-01
issue: "#23"
---

# feat(reports): Automated report generation from inspection data

## Overview

Implement the `generate_report` background task to compile inspection data into a structured HTML report,
and create the report detail view so owners can view reports in the dashboard. The Report model, task stub,
and submission flow (which queues the task) already exist — this issue fills in the generation logic, the
HTML template, and the viewing infrastructure.

## Problem Statement / Motivation

When an inspector submits an inspection, `submit_inspection` already queues `generate_report` via Django-Q2,
but the task is a stub returning `"pending_implementation"`. Property owners need reports generated
automatically and viewable in the dashboard to understand the condition of their apartments.

## Proposed Solution

1. **Implement `generate_report` task**: Create/update a Report record, render a standalone HTML template,
   store it in `html_content`, handle errors and idempotency.
2. **Create a standalone report HTML template**: Self-contained HTML (inline styles, no base template)
   suitable for future email/PDF use. German language, BAKY color tokens.
3. **Create report detail view**: Owner-accessible view at `/dashboard/reports/<id>/` with ownership
   verification through the `Report → Inspection → Apartment → Owner` chain.
4. **Create a photo proxy endpoint**: Serve photos via `/reports/photos/<id>/` that redirects to a fresh
   signed URL, solving the URL expiry problem for stored HTML.
5. **Wire up URLs**: Add report routes and include in root URLconf.

## Technical Considerations

### Photo URL Expiry Strategy

Photos use signed S3 URLs with 24h expiry. Embedding them directly in stored `html_content` would break
the report after 24 hours. Solution: reference photos in the HTML via an internal URL endpoint
(`/reports/photos/<photo_id>/`) that redirects to a freshly signed URL. The stored HTML is permanent;
photo URLs are resolved on each view.

### XSS Prevention

The stored HTML is rendered via `render_to_string()` which auto-escapes all template variables. The
report view renders `html_content` with `|safe` — since content was generated server-side from
auto-escaped templates, this is safe. No user input is marked `safe` at any point.

### Idempotency

The task uses `get_or_create` on the Report model. If a completed report already exists, it skips.
If pending/generating/failed, it regenerates. This handles Django-Q2 retries gracefully.

### Report–Email Race Condition

Both `generate_report` and `send_report_email` are queued simultaneously. Issue #24 (email delivery)
must handle this — the email task should check that `report.is_ready` before proceeding or retry.
This issue (#23) does NOT modify the email task stub or the submission view's task queuing.

### Category Ordering

Items are grouped by `category` and ordered by the minimum `order` value within each category
(first-appearance order), preserving the checklist template's intended flow.

### Duration Calculation

`completed_at - started_at` if both exist. Falls back to `completed_at - scheduled_at`. Shows "—" if
neither is available.

## System-Wide Impact

- **Interaction graph**: `submit_inspection` → `transaction.on_commit` → `queue_task("generate_report")` → Django-Q2 worker → `generate_report()` → creates/updates Report → renders template → stores HTML
- **Error propagation**: Task exceptions are caught inside the task, Report set to `failed` with error message. Django-Q2's `on_task_error` hook in `baky.tasks` also fires for logging.
- **State lifecycle risks**: If the task crashes between creating the Report (GENERATING) and completing it, the Report stays in GENERATING state. On retry, the task finds the existing Report and regenerates.
- **API surface parity**: No other interfaces generate reports. Admin can view reports via Django Admin.

## Acceptance Criteria

- [x] Report generated automatically on inspection submit (task already queued — just implement body)
- [ ] `generate_report` task creates Report with status transitions: PENDING → GENERATING → COMPLETED/FAILED
- [ ] Report contains all checklist results grouped by category
- [ ] Flagged items highlighted with severity, notes, and photos
- [ ] OK items shown in compact format
- [ ] N/A items shown in gray, grouped with their category
- [ ] Photo gallery section with all inspection photos
- [ ] Photos served via proxy endpoint (no URL expiry in stored HTML)
- [ ] Severity badges color-coded (emerald=OK, amber=Attention, rose=Urgent)
- [ ] Report header: BAKY branding, date, apartment address
- [ ] Report summary: Overall rating badge, inspector name, duration
- [ ] Inspector general notes section
- [ ] Report viewable at `/dashboard/reports/<id>/` with owner authentication
- [ ] Ownership verified: owner can only see reports for their apartments
- [ ] Non-owner gets 404 (not 403, per convention)
- [ ] Report in non-ready state shows appropriate status message
- [ ] Idempotent: duplicate task runs don't crash or create duplicate reports
- [ ] All user content auto-escaped (XSS safe)
- [ ] German language throughout the report
- [ ] Admin can re-trigger generation via custom action
- [ ] Generation completes within 5 minutes
- [ ] 15+ tests covering task, views, template rendering, permissions

## Implementation Plan (TDD Tasks)

### Task 1: Implement `generate_report` task — happy path

**Files**: `apps/reports/tasks.py`, `tests/reports/test_tasks.py`

**Test first** (`tests/reports/test_tasks.py`):

```python
@pytest.mark.django_db
class TestGenerateReportImplementation:
    def test_creates_report_for_completed_inspection(self):
        """generate_report creates a Report with COMPLETED status and non-empty html_content."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        InspectionItemFactory(inspection=inspection, category="Eingang", result=InspectionItem.Result.OK)
        InspectionItemFactory(inspection=inspection, category="Küche", result=InspectionItem.Result.FLAGGED,
                              severity=InspectionItem.Severity.MEDIUM, notes="Herd verschmutzt")

        result = generate_report(inspection.pk)

        assert result["status"] == "completed"
        report = Report.objects.get(inspection=inspection)
        assert report.status == Report.Status.COMPLETED
        assert report.html_content  # non-empty
        assert report.generated_at is not None
        assert "Eingang" in report.html_content
        assert "Küche" in report.html_content

    def test_report_html_contains_apartment_address(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert inspection.apartment.address in report.html_content

    def test_report_html_contains_overall_rating(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating=Inspection.OverallRating.OK)
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "OK" in report.html_content

    def test_report_groups_items_by_category(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        InspectionItemFactory(inspection=inspection, category="Eingang", order=1)
        InspectionItemFactory(inspection=inspection, category="Küche", order=2)
        InspectionItemFactory(inspection=inspection, category="Eingang", order=3)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        # Both Eingang items should be grouped together
        eingang_pos = report.html_content.index("Eingang")
        kuche_pos = report.html_content.index("Küche")
        assert eingang_pos < kuche_pos  # Eingang appears first (lower min order)
```

**Implementation** (`apps/reports/tasks.py`):
- Fetch inspection with `select_related("apartment", "apartment__owner", "inspector")` and `prefetch_related("items", "photos")`
- `Report.objects.get_or_create(inspection=inspection, defaults={"status": Report.Status.GENERATING})`
- If report already COMPLETED, return `{"status": "skipped", "reason": "already_completed"}`
- Set `report.status = GENERATING`, save
- Group items by category, ordered by min order value
- `render_to_string("reports/report.html", context)` with inspection data
- Store HTML, set `generated_at`, status = COMPLETED
- Return `{"report_id": report.pk, "status": "completed"}`

**Verify**: `make test ARGS="-k TestGenerateReportImplementation"`

### Task 2: Implement `generate_report` task — error handling and idempotency

**Files**: `apps/reports/tasks.py`, `tests/reports/test_tasks.py`

**Test first**:

```python
class TestGenerateReportErrorHandling:
    def test_sets_failed_status_on_template_error(self):
        """If rendering fails, report status should be FAILED with error_message."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        InspectionItemFactory(inspection=inspection)
        # Temporarily break the template to force a rendering error
        with patch("apps.reports.tasks.render_to_string", side_effect=Exception("Template error")):
            result = generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert report.status == Report.Status.FAILED
        assert "Template error" in report.error_message
        assert result["status"] == "failed"

    def test_skips_already_completed_report(self):
        """Idempotent: if report already completed, skip without error."""
        report = ReportFactory(status=Report.Status.COMPLETED)
        result = generate_report(report.inspection.pk)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_completed"

    def test_regenerates_failed_report(self):
        """A failed report should be regenerated on retry."""
        report = ReportFactory(status=Report.Status.FAILED, html_content="", generated_at=None)
        InspectionItemFactory(inspection=report.inspection)
        result = generate_report(report.inspection.pk)
        report.refresh_from_db()
        assert report.status == Report.Status.COMPLETED
        assert report.html_content  # non-empty
        assert result["status"] == "completed"

    def test_regenerates_pending_report(self):
        """A pending report (from crash) should be regenerated."""
        report = ReportFactory(status=Report.Status.PENDING, html_content="", generated_at=None)
        InspectionItemFactory(inspection=report.inspection)
        result = generate_report(report.inspection.pk)
        report.refresh_from_db()
        assert report.status == Report.Status.COMPLETED
```

**Implementation**: Add try/except around rendering. On exception, set `report.status = FAILED`, `report.error_message = str(e)`, save, return `{"status": "failed"}`. Add idempotency check at the start.

**Verify**: `make test ARGS="-k TestGenerateReportErrorHandling"`

### Task 3: Create the standalone report HTML template

**Files**: `templates/reports/report.html`

**Test first** (`tests/reports/test_tasks.py`):

```python
class TestReportTemplateRendering:
    def test_renders_flagged_items_with_severity_badge(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="attention")
        InspectionItemFactory(inspection=inspection, result=InspectionItem.Result.FLAGGED,
                              severity=InspectionItem.Severity.HIGH, notes="Schimmel entdeckt")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Schimmel entdeckt" in report.html_content
        assert "Hoch" in report.html_content  # Severity display

    def test_renders_ok_items_in_compact_format(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection, result=InspectionItem.Result.OK,
                              checklist_label="Tür schließt korrekt")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Tür schließt korrekt" in report.html_content

    def test_renders_na_items(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection, result=InspectionItem.Result.NA,
                              checklist_label="Gaskontrolle")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Gaskontrolle" in report.html_content
        assert "N/A" in report.html_content

    def test_renders_inspector_general_notes(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED,
                                       general_notes="Alles in Ordnung, sehr gepflegt.")
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Alles in Ordnung, sehr gepflegt." in report.html_content

    def test_renders_with_german_umlauts(self):
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        InspectionItemFactory(inspection=inspection, category="Küche",
                              checklist_label="Kühlschrank überprüfen", notes="Türdichtung löst sich")
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "Kühlschrank überprüfen" in report.html_content
        assert "Türdichtung löst sich" in report.html_content

    def test_html_is_self_contained(self):
        """Report HTML should be a complete document — not extending a base template."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED, overall_rating="ok")
        InspectionItemFactory(inspection=inspection)
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert "<!DOCTYPE html>" in report.html_content or "<html" in report.html_content

    def test_escapes_user_content(self):
        """XSS prevention: user-generated content must be escaped."""
        inspection = InspectionFactory(status=Inspection.Status.COMPLETED)
        InspectionItemFactory(inspection=inspection,
                              notes='<script>alert("xss")</script>')
        generate_report(inspection.pk)
        report = Report.objects.get(inspection=inspection)
        assert '<script>' not in report.html_content
        assert '&lt;script&gt;' in report.html_content
```

**Implementation** (`templates/reports/report.html`):
- Standalone HTML document with `<!DOCTYPE html>`, `<html lang="de">`
- Inline CSS using BAKY color tokens (slate-800, amber-500, emerald-500, rose-500)
- Header: BAKY text branding, report date, apartment address
- Summary section: Overall rating badge (color-coded), inspector name, duration
- Findings grouped by category, each category as a section
- Flagged items: severity badge, notes, photo references
- OK items: compact single-line with green checkmark
- N/A items: gray text
- Photo gallery section (photos referenced via `/reports/photos/<id>/` proxy URL)
- Inspector general notes section
- All labels in German

**Verify**: `make test ARGS="-k TestReportTemplateRendering"`

### Task 4: Create photo proxy view

**Files**: `apps/reports/views.py`, `apps/reports/urls.py`, `tests/reports/test_views.py`

**Test first** (`tests/reports/test_views.py`):

```python
@pytest.mark.django_db
class TestReportPhotoView:
    def test_redirects_to_signed_url(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection)
        photo = PhotoFactory(inspection=inspection)
        client.force_login(owner)
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 302  # redirect to signed URL

    def test_requires_authentication(self, client):
        photo = PhotoFactory()
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 302  # redirect to login

    def test_returns_404_for_wrong_owner(self, client):
        other_owner = OwnerFactory()
        photo = PhotoFactory()
        client.force_login(other_owner)
        response = client.get(f"/reports/photos/{photo.pk}/")
        assert response.status_code == 404

    def test_returns_404_for_nonexistent_photo(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get("/reports/photos/999999/")
        assert response.status_code == 404
```

**Implementation** (`apps/reports/views.py`):
- `report_photo(request, photo_id)` view with `@owner_required`
- Fetch photo with `select_related("inspection__apartment__owner")`
- Verify `photo.inspection.apartment.owner == request.user`
- Redirect to `photo.get_file_url()` (fresh signed URL)

**URL**: `path("photos/<int:photo_id>/", views.report_photo, name="report_photo")`

**Verify**: `make test ARGS="-k TestReportPhotoView"`

### Task 5: Create report detail view for owners

**Files**: `apps/reports/views.py`, `apps/reports/urls.py`, `templates/reports/report_detail.html`, `tests/reports/test_views.py`

**Test first** (`tests/reports/test_views.py`):

```python
@pytest.mark.django_db
class TestReportDetailView:
    def test_owner_can_view_own_report(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection)
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 200
        assert report.html_content in response.content.decode()

    def test_requires_owner_role(self, client):
        inspector = InspectorFactory()
        report = ReportFactory()
        client.force_login(inspector)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 302  # redirect (role check)

    def test_returns_404_for_other_owners_report(self, client):
        owner = OwnerFactory()
        other_owner = OwnerFactory()
        apartment = ApartmentFactory(owner=other_owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection)
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 404

    def test_unauthenticated_redirects_to_login(self, client):
        report = ReportFactory()
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 302

    def test_pending_report_shows_status_message(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection, status=Report.Status.PENDING, html_content="")
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 200
        assert "wird erstellt" in response.content.decode().lower() or "Ausstehend" in response.content.decode()

    def test_failed_report_shows_error_message(self, client):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        inspection = InspectionFactory(apartment=apartment, status=Inspection.Status.COMPLETED)
        report = ReportFactory(inspection=inspection, status=Report.Status.FAILED, html_content="",
                               error_message="Template error")
        client.force_login(owner)
        response = client.get(f"/dashboard/reports/{report.pk}/")
        assert response.status_code == 200
```

**Implementation**:
- `report_detail(request, report_id)` view with `@owner_required`
- Fetch report with `select_related("inspection__apartment__owner")`
- Verify `report.inspection.apartment.owner == request.user`, else 404
- If `report.is_ready`: render `reports/report_detail.html` which embeds `html_content|safe`
- If pending/generating: show status message with HTMX polling
- If failed: show error state

**Template** (`templates/reports/report_detail.html`):
- Extends `dashboard/base_dashboard.html`
- Renders `report.html_content|safe` in an iframe or content div
- Status indicators for pending/generating/failed states

**URL**: Wire into dashboard namespace: `path("reports/<int:report_id>/", views.report_detail, name="report_detail")`

**Verify**: `make test ARGS="-k TestReportDetailView"`

### Task 6: Wire up URLs in root URLconf

**Files**: `apps/reports/urls.py`, `baky/urls.py`

**Test first**: The view tests from Tasks 4-5 already verify URL routing works.

**Implementation**:
- `apps/reports/urls.py`: Add `report_photo` under the `reports` namespace
- `baky/urls.py`: Add `path("reports/", include("apps.reports.urls"))` for photo proxy
- Report detail view goes under dashboard URLs: add route in `apps/dashboard/urls.py` or add to reports urls and include under dashboard prefix

**Verify**: `make test`

### Task 7: Admin action to re-trigger report generation

**Files**: `apps/reports/admin.py`, `tests/reports/test_admin.py` (optional)

**Implementation** (`apps/reports/admin.py`):
- Add custom admin action `regenerate_reports` that queues `generate_report` for selected reports
- Label: "Bericht(e) neu erstellen"

**Verify**: `make test && make lint`

### Task 8: Final validation and cleanup

**Verify all acceptance criteria**:
```bash
make lint
make test
make manage CMD="check"
```

Ensure 15+ tests total across `test_tasks.py` and `test_views.py`.

## Dependencies & Risks

- **Dependency**: Report model exists (done in #12)
- **Dependency**: Inspection submission flow queues task (done in #22)
- **Risk**: Photo signed URL approach — if S3 is down, photo proxy returns 404. Acceptable for MVP.
- **Risk**: Large inspections (50+ photos) could slow rendering. Template is simple HTML — unlikely to hit 120s timeout.

## Sources & References

### Internal References
- Report model: `apps/reports/models.py`
- Task stub: `apps/reports/tasks.py:6-23`
- Submission flow: `apps/inspections/views.py:380-434`
- Photo model: `apps/inspections/models.py:180-225`
- Queue helper: `baky/tasks.py:15`
- Factories: `tests/factories.py:106-113`
- Template comment gotcha: `docs/solutions/runtime-errors/django-template-tags-in-html-comments-recursion.md`

### Related Work
- Issue #23: https://github.com/robert197/baky/issues/23
- Issue #24 (email delivery): depends on this issue
- Issue #16 (owner dashboard): will link to report detail view
