---
title: "feat: Implement email delivery for inspection reports"
type: feat
status: active
date: 2026-04-01
issue: "#24"
---

# feat: Implement email delivery for inspection reports

## Overview

Send inspection reports and notifications to property owners via email using django-anymail with Resend API. Four email task stubs already exist in the codebase; this plan implements them and adds the infrastructure to support HTML email delivery in both local dev (Mailpit) and production (Resend).

## Problem Statement

After inspection submission, the system generates an HTML report but has no way to deliver it to the property owner. All four email-sending task stubs (`send_report_email`, `send_urgent_notification`, `send_owner_reminder`, `send_inspection_reminder`) log a message and return `"pending_implementation"`. Additionally, the worker service cannot send emails in local dev because it's missing the Mailpit env vars.

## Proposed Solution

1. Replace `resend>=2.0` with `django-anymail[resend]` for production email delivery
2. Fix the race condition between report generation and email sending by chaining tasks
3. Add `email_sent_at` to the Report model for idempotency and tracking
4. Create HTML email templates (table-based, inline CSS) matching BAKY design tokens
5. Implement all four email task stubs with proper guard clauses and idempotency
6. Add admin action to resend report emails

## Key Architectural Decisions

**Race condition fix**: `generate_report` will queue `send_report_email` as its last step on success, replacing the current simultaneous queuing in `submit_inspection`. This is the simplest and most reliable approach.

**Email backend**: `django-anymail` with Resend backend for production. No code changes needed for local dev — existing Mailpit SMTP setup works. The `resend` SDK is not needed when using anymail.

**Idempotency**: `email_sent_at` timestamp on Report model. Email tasks check this before sending. No separate `EmailLog` model for MVP — the Report model is sufficient since report emails are the primary use case.

**Photo handling in emails**: Emails link to the full web report rather than embedding photos. This avoids signed URL expiry issues and keeps email size small.

**Report link**: Links to the authenticated report view. No token-based access for MVP — owners are professional users who use the platform regularly.

**SITE_URL setting**: Added to base settings so background tasks can construct absolute URLs without an HTTP request context.

## Technical Considerations

### System-Wide Impact

- **Interaction graph**: `submit_inspection` → `transaction.on_commit` → `generate_report` → (on success) `send_report_email`. Removes direct `send_report_email` queue call from `submit_inspection`. Urgent notification remains directly queued from submit.
- **Error propagation**: Anymail raises `AnymailAPIError` on Resend failures. Django-Q2 retries on timeout (120s/180s). Email tasks are idempotent via `email_sent_at` check.
- **State lifecycle**: Report model gains `email_sent_at`. Partial failure (report generated but email fails) leaves `email_sent_at=None` — safe to retry.
- **Worker env**: Worker service needs `EMAIL_HOST=mailpit` and `EMAIL_PORT=1025` in docker-compose.yml for local email delivery.

### Dependencies

- `django-anymail[resend]>=14.0` — replaces `resend>=2.0` in `requirements/base.txt`
- No new models — only a migration adding `email_sent_at` to Report

## Acceptance Criteria

- [ ] Report email sent after inspection submission (chained from `generate_report`)
- [ ] Urgent alert sent immediately on inspection submit when rating is URGENT
- [ ] Owner reminder sent day-before via management command
- [ ] Inspector reminder sent day-before via management command
- [ ] All emails have HTML + plain text versions
- [ ] German language throughout all email content
- [ ] Emails render with BAKY branding (navy/amber color scheme)
- [ ] `email_sent_at` prevents duplicate report emails on retry
- [ ] Worker sends emails through Mailpit in local dev
- [ ] Production settings configure Resend via anymail
- [ ] Admin can resend report emails
- [ ] All existing tests continue to pass
- [ ] 20+ new tests covering email delivery

---

## Implementation Tasks

### Task 1: Fix worker email config in docker-compose.yml

**Files**: `docker-compose.yml`

**Test** (manual verification):
```bash
# After change, restart worker and verify it picks up Mailpit
make down && make up
# Check worker logs for email backend
make manage CMD="shell -c \"from django.conf import settings; print(settings.EMAIL_BACKEND)\""
```

**Implementation**:
Add `EMAIL_HOST=mailpit` and `EMAIL_PORT=1025` to the worker service environment in `docker-compose.yml` (lines 46-49), matching the web service.

**Verify**: `make down && make up` — worker should now route emails through Mailpit.

---

### Task 2: Replace resend with django-anymail in requirements

**Files**: `requirements/base.txt`

**Implementation**:
Replace `resend>=2.0` (line 19) with `django-anymail[resend]>=14.0`.

**Verify**: `make build` (rebuilds Docker image with new dependency).

---

### Task 3: Configure production email backend

**Files**: `baky/settings/base.py`, `baky/settings/production.py`

**Test** (`tests/test_settings.py` — new):
```python
def test_base_settings_has_site_url():
    from django.conf import settings
    assert hasattr(settings, "SITE_URL")

def test_base_settings_default_from_email():
    from django.conf import settings
    assert "baky" in settings.DEFAULT_FROM_EMAIL.lower()
```

**Implementation**:

1. In `baky/settings/base.py`, add after the email section:
   ```python
   SITE_URL = env("SITE_URL", default="http://localhost:8010")
   ```

2. In `baky/settings/production.py`, add email configuration:
   ```python
   # Email via Resend (through django-anymail)
   INSTALLED_APPS += ["anymail"]
   EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
   ANYMAIL = {
       "RESEND_API_KEY": env("RESEND_API_KEY"),
   }
   SITE_URL = env("SITE_URL")
   ```

**Verify**: `make test` — settings tests pass.

---

### Task 4: Add email_sent_at to Report model + migration

**Files**: `apps/reports/models.py`, new migration

**Test** (`tests/reports/test_models.py`):
```python
def test_report_email_sent_at_defaults_to_none(report):
    assert report.email_sent_at is None

def test_report_email_sent_at_can_be_set(report):
    from django.utils import timezone
    report.email_sent_at = timezone.now()
    report.save()
    report.refresh_from_db()
    assert report.email_sent_at is not None
```

**Implementation**:
Add to Report model:
```python
email_sent_at = models.DateTimeField(null=True, blank=True, help_text="When the report email was sent to the owner")
```

Run `make makemigrations` and `make migrate`.

**Verify**: `make test` — model tests pass.

---

### Task 5: Create HTML email base template

**Files**: `templates/emails/_base.html`

**Test** (`tests/reports/test_email_templates.py`):
```python
from django.template.loader import render_to_string

def test_email_base_template_renders():
    html = render_to_string("emails/_base.html", {
        "subject": "Test",
        "content": "<p>Hello</p>",
    })
    assert "BAKY" in html
    assert "Hello" in html
    assert "<table" in html  # table-based layout

def test_email_base_template_has_inline_styles():
    html = render_to_string("emails/_base.html", {
        "subject": "Test",
        "content": "<p>Test</p>",
    })
    assert 'style="' in html
    assert "#1e293b" in html  # primary color
```

**Implementation**:
Create `templates/emails/_base.html` — a table-based HTML email layout with:
- 600px max-width centered table
- BAKY logo/text header with navy (#1e293b) background
- White content area
- Footer with "BAKY — Betreuung. Absicherung. Kontrolle. Your Home." and muted text
- All styles inline (no `<style>` block for maximum client compatibility)
- Uses BAKY color tokens: primary (#1e293b), accent (#f59e0b), surface (#f8fafc)
- `{% block content %}{% endblock %}` for child templates
- `{% block preheader %}{% endblock %}` for email preview text

**Verify**: `make test` — template render tests pass.

---

### Task 6: Create report email template (HTML + plain text)

**Files**: `templates/emails/report_email.html`, `templates/emails/report_email.txt`

**Test** (`tests/reports/test_email_templates.py`):
```python
def test_report_email_html_template_renders(completed_inspection):
    html = render_to_string("emails/report_email.html", {
        "inspection": completed_inspection,
        "apartment": completed_inspection.apartment,
        "report_url": "https://baky.at/reports/1/",
        "rating_display": "OK",
        "flagged_items": [],
    })
    assert completed_inspection.apartment.address in html
    assert "Inspektionsbericht" in html
    assert "https://baky.at/reports/1/" in html

def test_report_email_txt_template_renders(completed_inspection):
    txt = render_to_string("emails/report_email.txt", {
        "inspection": completed_inspection,
        "apartment": completed_inspection.apartment,
        "report_url": "https://baky.at/reports/1/",
        "rating_display": "OK",
        "flagged_items": [],
    })
    assert completed_inspection.apartment.address in txt
    assert "https://baky.at/reports/1/" in txt
```

**Implementation**:

HTML template extends `emails/_base.html`:
- Summary: rating badge (color-coded OK/Attention/Urgent), date, inspector name
- Flagged items list (if any): item name, category, inspector notes
- CTA button: "Vollständigen Bericht ansehen" linking to report URL
- Text: "Dieser Bericht wurde automatisch erstellt."

Plain text template:
- Same content as HTML but formatted for plain text readers
- Report URL on its own line for easy clicking

**Verify**: `make test`

---

### Task 7: Create urgent alert email template (HTML + plain text)

**Files**: `templates/emails/urgent_alert.html`, `templates/emails/urgent_alert.txt`

**Test** (`tests/reports/test_email_templates.py`):
```python
def test_urgent_alert_html_renders(completed_inspection, flagged_items):
    html = render_to_string("emails/urgent_alert.html", {
        "inspection": completed_inspection,
        "apartment": completed_inspection.apartment,
        "flagged_items": flagged_items,
        "report_url": "https://baky.at/reports/1/",
    })
    assert "Dringend" in html or "DRINGEND" in html
    assert completed_inspection.apartment.address in html
```

**Implementation**:

HTML template extends `emails/_base.html`:
- Red/danger header banner with warning icon
- Address and inspection date
- List of urgent/flagged items with inspector notes
- CTA: "Bericht ansehen"
- Footer note: "Bei Fragen kontaktieren Sie uns unter support@baky.at"

**Verify**: `make test`

---

### Task 8: Create reminder email templates (HTML + plain text)

**Files**: `templates/emails/owner_reminder.html`, `templates/emails/owner_reminder.txt`, `templates/emails/inspector_reminder.html`, `templates/emails/inspector_reminder.txt`

**Test** (`tests/inspections/test_email_templates.py`):
```python
def test_owner_reminder_html_renders(scheduled_inspection):
    html = render_to_string("emails/owner_reminder.html", {
        "inspection": scheduled_inspection,
        "apartment": scheduled_inspection.apartment,
        "scheduled_date": "02.04.2026",
        "scheduled_time": "10:00",
    })
    assert scheduled_inspection.apartment.address in html
    assert "morgen" in html.lower() or "Inspektion" in html

def test_inspector_reminder_html_renders(scheduled_inspection):
    html = render_to_string("emails/inspector_reminder.html", {
        "inspection": scheduled_inspection,
        "apartment": scheduled_inspection.apartment,
        "scheduled_date": "02.04.2026",
        "scheduled_time": "10:00",
    })
    assert scheduled_inspection.apartment.address in html
```

**Implementation**:

Owner reminder:
- Subject: "BAKY Inspektion morgen — [Address]"
- Content: date, time, address, what will be checked (checklist categories)

Inspector reminder:
- Subject: "BAKY Inspektion morgen — [Address]"
- Content: date, time, address, apartment owner name, checklist items count

**Verify**: `make test`

---

### Task 9: Fix race condition — chain send_report_email from generate_report

**Files**: `apps/reports/tasks.py`, `apps/inspections/views.py`

**Test** (`tests/reports/test_tasks.py`):
```python
@patch("baky.tasks.queue_task")
def test_generate_report_queues_email_on_success(mock_queue, completed_inspection):
    result = generate_report(completed_inspection.pk)
    assert result["status"] == "completed"
    mock_queue.assert_called_once_with(
        "apps.reports.tasks.send_report_email",
        completed_inspection.pk,
        task_name=f"send_report_email_{completed_inspection.pk}",
    )

@patch("baky.tasks.queue_task")
def test_generate_report_skips_email_on_failure(mock_queue, completed_inspection):
    # Force a render failure
    with patch("apps.reports.tasks._render_report_html", side_effect=Exception("boom")):
        result = generate_report(completed_inspection.pk)
    assert result["status"] == "failed"
    mock_queue.assert_not_called()
```

**Test** (`tests/inspections/test_submission_views.py` — update existing):
```python
@patch("baky.tasks.queue_task")
def test_submit_inspection_does_not_queue_send_report_email_directly(mock_queue, ...):
    # submit_inspection should only queue generate_report, not send_report_email
    # (email is chained from generate_report on success)
    response = client.post(submit_url, data)
    queued_tasks = [call.args[0] for call in mock_queue.call_args_list]
    assert "apps.reports.tasks.generate_report" in queued_tasks
    assert "apps.reports.tasks.send_report_email" not in queued_tasks
```

**Implementation**:

1. In `apps/reports/tasks.py` `generate_report()`, after the report is saved as COMPLETED (line 61), add:
   ```python
   from baky.tasks import queue_task
   queue_task(
       "apps.reports.tasks.send_report_email",
       inspection_id,
       task_name=f"send_report_email_{inspection_id}",
   )
   ```

2. In `apps/inspections/views.py` `_queue_post_submit_tasks()` (line 413-429), remove the `send_report_email` queue call (lines 419-423).

**Verify**: `make test` — all submission and report tests pass.

---

### Task 10: Implement send_report_email task

**Files**: `apps/reports/tasks.py`

**Test** (`tests/reports/test_tasks.py`):
```python
def test_send_report_email_sends_html_email(completed_inspection):
    """Report with is_ready=True sends an email to the owner."""
    from apps.reports.models import Report
    report = Report.objects.get(inspection=completed_inspection)
    report.status = Report.Status.COMPLETED
    report.html_content = "<p>Test report</p>"
    report.save()

    result = send_report_email(completed_inspection.pk)

    assert result["status"] == "sent"
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [completed_inspection.apartment.owner.email]
    assert "Inspektionsbericht" in email.subject
    assert completed_inspection.apartment.address in email.subject
    assert len(email.alternatives) == 1  # HTML version

    report.refresh_from_db()
    assert report.email_sent_at is not None

def test_send_report_email_skips_if_already_sent(completed_inspection):
    """Idempotency: does not re-send if email_sent_at is set."""
    from apps.reports.models import Report
    report = Report.objects.get(inspection=completed_inspection)
    report.status = Report.Status.COMPLETED
    report.html_content = "<p>Test</p>"
    report.email_sent_at = timezone.now()
    report.save()

    result = send_report_email(completed_inspection.pk)
    assert result["status"] == "skipped"
    assert result["reason"] == "already_sent"
    assert len(mail.outbox) == 0

def test_send_report_email_skips_if_report_not_ready(completed_inspection):
    """If report is not yet generated, skip (will be retried by chain)."""
    from apps.reports.models import Report
    report = Report.objects.get(inspection=completed_inspection)
    report.status = Report.Status.GENERATING
    report.save()

    result = send_report_email(completed_inspection.pk)
    assert result["status"] == "skipped"
    assert result["reason"] == "report_not_ready"
    assert len(mail.outbox) == 0

def test_send_report_email_skips_if_no_report_exists(completed_inspection):
    """If report doesn't exist yet, skip gracefully."""
    from apps.reports.models import Report
    Report.objects.filter(inspection=completed_inspection).delete()

    result = send_report_email(completed_inspection.pk)
    assert result["status"] == "skipped"
    assert result["reason"] == "no_report"

def test_send_report_email_subject_format(completed_inspection):
    """Subject follows format: BAKY Inspektionsbericht — [Address] — [Date]"""
    from apps.reports.models import Report
    report = Report.objects.get(inspection=completed_inspection)
    report.status = Report.Status.COMPLETED
    report.html_content = "<p>Test</p>"
    report.save()

    send_report_email(completed_inspection.pk)

    email = mail.outbox[0]
    date_str = completed_inspection.completed_at.strftime("%d.%m.%Y")
    expected_subject = f"BAKY Inspektionsbericht — {completed_inspection.apartment.address} — {date_str}"
    assert email.subject == expected_subject
```

**Implementation**:

Replace the stub in `apps/reports/tasks.py`:

```python
def send_report_email(inspection_id: int) -> dict:
    from apps.inspections.models import Inspection
    from apps.reports.models import Report

    inspection = Inspection.objects.select_related("apartment__owner").get(pk=inspection_id)

    try:
        report = Report.objects.get(inspection=inspection)
    except Report.DoesNotExist:
        logger.warning("No report for inspection %d, skipping email", inspection_id)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "no_report"}

    if not report.is_ready:
        logger.info("Report %d not ready for inspection %d, skipping", report.pk, inspection_id)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "report_not_ready"}

    if report.email_sent_at:
        logger.info("Email already sent for report %d at %s", report.pk, report.email_sent_at)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "already_sent"}

    owner = inspection.apartment.owner
    apartment = inspection.apartment
    date_str = inspection.completed_at.strftime("%d.%m.%Y")
    subject = f"BAKY Inspektionsbericht — {apartment.address} — {date_str}"

    report_url = f"{settings.SITE_URL}/reports/{report.pk}/"
    flagged_items = list(inspection.items.exclude(status="ok").exclude(status="na"))

    context = {
        "inspection": inspection,
        "apartment": apartment,
        "report_url": report_url,
        "rating_display": inspection.get_overall_rating_display(),
        "flagged_items": flagged_items,
    }

    html_body = render_to_string("emails/report_email.html", context)
    text_body = render_to_string("emails/report_email.txt", context)

    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [owner.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()

    report.email_sent_at = timezone.now()
    report.save(update_fields=["email_sent_at", "updated_at"])

    logger.info("Report email sent to %s for inspection %d", owner.email, inspection_id)
    return {"inspection_id": inspection_id, "owner_email": owner.email, "status": "sent"}
```

**Verify**: `make test`

---

### Task 11: Implement send_urgent_notification task

**Files**: `apps/inspections/tasks.py`

**Test** (`tests/inspections/test_tasks.py`):
```python
def test_send_urgent_notification_sends_email(urgent_inspection):
    result = send_urgent_notification(urgent_inspection.pk)
    assert result["status"] == "sent"
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert "Dringend" in email.subject or "dringend" in email.subject.lower()
    assert urgent_inspection.apartment.address in email.subject
    assert email.to == [urgent_inspection.apartment.owner.email]
    assert len(email.alternatives) == 1

def test_send_urgent_notification_skips_non_urgent(completed_inspection):
    """Non-urgent inspection should be skipped."""
    result = send_urgent_notification(completed_inspection.pk)
    assert result["status"] == "skipped"
    assert len(mail.outbox) == 0

def test_send_urgent_notification_skips_non_completed(scheduled_inspection):
    result = send_urgent_notification(scheduled_inspection.pk)
    assert result["status"] == "skipped"
    assert len(mail.outbox) == 0
```

**Implementation**:

Replace the stub, keeping existing guard clauses. Add email sending:

```python
def send_urgent_notification(inspection_id: int) -> dict:
    # ... existing guard clauses for status and rating ...

    flagged_items = list(inspection.items.exclude(status="ok").exclude(status="na"))
    report_url = f"{settings.SITE_URL}/reports/{inspection.pk}/"  # may not exist yet

    context = {
        "inspection": inspection,
        "apartment": inspection.apartment,
        "flagged_items": flagged_items,
        "report_url": report_url,
    }

    subject = f"BAKY Dringender Fund — {inspection.apartment.address}"
    html_body = render_to_string("emails/urgent_alert.html", context)
    text_body = render_to_string("emails/urgent_alert.txt", context)

    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [owner.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()

    return {"inspection_id": inspection_id, "owner_email": owner.email, "status": "sent"}
```

**Verify**: `make test`

---

### Task 12: Implement send_owner_reminder task

**Files**: `apps/inspections/tasks.py`

**Test** (`tests/inspections/test_tasks.py`):
```python
def test_send_owner_reminder_sends_email(scheduled_inspection):
    result = send_owner_reminder(scheduled_inspection.pk)
    assert result["status"] == "sent"
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert "morgen" in email.subject.lower() or "Inspektion" in email.subject
    assert scheduled_inspection.apartment.address in email.subject
    assert email.to == [scheduled_inspection.apartment.owner.email]

def test_send_owner_reminder_skips_non_scheduled(completed_inspection):
    result = send_owner_reminder(completed_inspection.pk)
    assert result["status"] == "skipped"
    assert len(mail.outbox) == 0
```

**Implementation**:

Replace the stub, keeping existing guard clauses:

```python
def send_owner_reminder(inspection_id: int) -> dict:
    # ... existing guard clauses ...

    subject = f"BAKY Inspektion morgen — {inspection.apartment.address}"
    scheduled_date = inspection.scheduled_at.strftime("%d.%m.%Y")
    scheduled_time = inspection.scheduled_at.strftime("%H:%M")

    context = {
        "inspection": inspection,
        "apartment": inspection.apartment,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
    }

    html_body = render_to_string("emails/owner_reminder.html", context)
    text_body = render_to_string("emails/owner_reminder.txt", context)

    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [owner.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()

    return {"inspection_id": inspection_id, "owner_email": owner.email, "status": "sent"}
```

**Verify**: `make test`

---

### Task 13: Implement send_inspection_reminder task

**Files**: `apps/inspections/tasks.py`

**Test** (`tests/inspections/test_tasks.py`):
```python
def test_send_inspection_reminder_sends_email(scheduled_inspection):
    result = send_inspection_reminder(scheduled_inspection.pk)
    assert result["status"] == "sent"
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [scheduled_inspection.inspector.email]
    assert scheduled_inspection.apartment.address in email.subject

def test_send_inspection_reminder_skips_non_scheduled(completed_inspection):
    result = send_inspection_reminder(completed_inspection.pk)
    assert result["status"] == "skipped"
    assert len(mail.outbox) == 0

def test_send_inspection_reminder_skips_past_due(past_inspection):
    result = send_inspection_reminder(past_inspection.pk)
    assert result["status"] == "skipped"
    assert result["reason"] == "past_due"
```

**Implementation**:

Replace the stub, keeping existing guard clauses:

```python
def send_inspection_reminder(inspection_id: int) -> dict:
    # ... existing guard clauses for status and past_due ...

    subject = f"BAKY Inspektion morgen — {inspection.apartment.address}"
    scheduled_date = inspection.scheduled_at.strftime("%d.%m.%Y")
    scheduled_time = inspection.scheduled_at.strftime("%H:%M")

    context = {
        "inspection": inspection,
        "apartment": inspection.apartment,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
    }

    html_body = render_to_string("emails/inspector_reminder.html", context)
    text_body = render_to_string("emails/inspector_reminder.txt", context)

    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [inspection.inspector.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()

    return {"inspection_id": inspection_id, "inspector_email": inspection.inspector.email, "status": "sent"}
```

**Verify**: `make test`

---

### Task 14: Add admin action to resend report email

**Files**: `apps/reports/admin.py`

**Test** (`tests/reports/test_admin.py`):
```python
def test_resend_report_email_admin_action(admin_client, completed_report):
    url = reverse("admin:reports_report_changelist")
    response = admin_client.post(url, {
        "action": "resend_report_email",
        "_selected_action": [completed_report.pk],
    })
    assert response.status_code == 302
    # Verify email_sent_at was cleared and task was queued
    completed_report.refresh_from_db()
    assert completed_report.email_sent_at is None
```

**Implementation**:

Add to `ReportAdmin`:
```python
@admin.action(description="Bericht-E-Mail erneut senden")
def resend_report_email(self, request, queryset):
    count = 0
    for report in queryset.filter(status=Report.Status.COMPLETED):
        report.email_sent_at = None
        report.save(update_fields=["email_sent_at", "updated_at"])
        queue_task(
            "apps.reports.tasks.send_report_email",
            report.inspection_id,
            task_name=f"resend_report_email_{report.inspection_id}",
        )
        count += 1
    self.message_user(request, f"{count} Bericht-E-Mail(s) erneut gesendet.")
```

Add `resend_report_email` to the `actions` list.

**Verify**: `make test`

---

### Task 15: Integration test — full inspection-to-email flow

**Files**: `tests/reports/test_email_integration.py`

**Test**:
```python
def test_full_inspection_to_email_flow(completed_inspection):
    """End-to-end: generate_report → send_report_email → owner receives email."""
    result = generate_report(completed_inspection.pk)
    assert result["status"] == "completed"

    # Simulate the chained task
    email_result = send_report_email(completed_inspection.pk)
    assert email_result["status"] == "sent"
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert email.to == [completed_inspection.apartment.owner.email]
    assert "Inspektionsbericht" in email.subject
    assert len(email.alternatives) == 1

    # Verify idempotency
    email_result2 = send_report_email(completed_inspection.pk)
    assert email_result2["status"] == "skipped"
    assert email_result2["reason"] == "already_sent"
    assert len(mail.outbox) == 1  # no second email

def test_urgent_inspection_sends_both_emails(urgent_inspection):
    """Urgent inspection sends both urgent alert and report email."""
    # Urgent notification sent immediately
    urgent_result = send_urgent_notification(urgent_inspection.pk)
    assert urgent_result["status"] == "sent"

    # Report generated and email chained
    report_result = generate_report(urgent_inspection.pk)
    assert report_result["status"] == "completed"

    email_result = send_report_email(urgent_inspection.pk)
    assert email_result["status"] == "sent"

    assert len(mail.outbox) == 2  # urgent alert + report email
```

**Verify**: `make test`

---

## Summary of Files Changed

| File | Change |
|------|--------|
| `docker-compose.yml` | Add EMAIL_HOST/PORT to worker service |
| `requirements/base.txt` | Replace `resend>=2.0` with `django-anymail[resend]>=14.0` |
| `baky/settings/base.py` | Add SITE_URL setting |
| `baky/settings/production.py` | Add anymail + Resend email backend config |
| `apps/reports/models.py` | Add `email_sent_at` field |
| `apps/reports/tasks.py` | Implement `send_report_email`, chain from `generate_report` |
| `apps/reports/admin.py` | Add resend email admin action |
| `apps/inspections/tasks.py` | Implement 3 email task stubs |
| `apps/inspections/views.py` | Remove direct `send_report_email` queue call |
| `templates/emails/_base.html` | New: HTML email base template |
| `templates/emails/report_email.html` | New: report email HTML |
| `templates/emails/report_email.txt` | New: report email plain text |
| `templates/emails/urgent_alert.html` | New: urgent alert HTML |
| `templates/emails/urgent_alert.txt` | New: urgent alert plain text |
| `templates/emails/owner_reminder.html` | New: owner reminder HTML |
| `templates/emails/owner_reminder.txt` | New: owner reminder plain text |
| `templates/emails/inspector_reminder.html` | New: inspector reminder HTML |
| `templates/emails/inspector_reminder.txt` | New: inspector reminder plain text |
| `tests/reports/test_email_templates.py` | New: template render tests |
| `tests/reports/test_tasks.py` | New/updated: task tests |
| `tests/reports/test_email_integration.py` | New: integration tests |
| `tests/inspections/test_tasks.py` | New: inspection email task tests |
| `tests/inspections/test_email_templates.py` | New: reminder template tests |

## Out of Scope (Follow-up Issues)

- Token-based unauthenticated report access links
- Email preference / unsubscribe management
- Batch daily digest for multi-apartment owners
- Migration of existing verification/welcome emails to HTML templates
- Webhook-based delivery tracking (bounces, opens)
- CSS inliner integration (e.g., `css-inline`) — for MVP, inline styles are hand-written in templates
- Email sending rate limiter — natural throttling via 2 Django-Q2 workers is sufficient at MVP scale
