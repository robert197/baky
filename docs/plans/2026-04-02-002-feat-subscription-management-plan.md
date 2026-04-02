---
title: "feat: Subscription management for owner dashboard"
type: feat
status: completed
date: 2026-04-02
---

# Subscription Management for Owner Dashboard

## Overview

Add subscription management pages to the owner dashboard so property owners can view their current plan, request changes, pause/cancel their subscription, book extra inspections, and view billing history. All changes are admin-mediated (no Stripe in MVP) — requests send email notifications to the admin team.

## Problem Statement / Motivation

Owners currently have no visibility into their subscription status from the dashboard. They cannot see their plan, request changes, or manage their subscription without contacting support directly. This is a critical gap in the self-service dashboard experience.

## Proposed Solution

Add 6 new views to the dashboard app under `/dashboard/subscription/`:

1. **Subscription overview** — displays plan, status, billing info, usage stats
2. **Plan change request** — form to request upgrade/downgrade, sends admin email
3. **Pause request** — form to request subscription pause, sends admin email
4. **Cancel request** — form to request cancellation, sends admin email
5. **Extra inspection booking** — form to book additional inspection, sends admin email
6. **Billing history** — placeholder page for MVP (empty state)

Additionally, add a subscription summary card to the main dashboard index page and activate the "Einstellungen" sidebar link.

## Technical Considerations

### Existing Subscription Model

The `Subscription` model at `apps/accounts/models.py:39` already has `plan`, `status`, `billing_cycle`, and `started_at`. Two additions needed:

- `PLAN_PRICES` dict (mirrors `PLAN_INSPECTION_LIMITS` pattern)
- `get_monthly_price()` and `get_next_billing_date()` helper methods

### OneToOneField Guard (Documented Learning)

Per `docs/solutions/runtime-errors/django-reverse-onetoone-relatedobjectdoesnotexist-in-templates.md`: accessing `user.subscription` in templates crashes with `RelatedObjectDoesNotExist` when no subscription exists. Must use `Exists()` annotation or `hasattr` guard in views. Every view must handle the "no subscription" case by showing a CTA to contact support.

### Admin Notification Email Pattern

Follow existing pattern from `apps/inspections/tasks.py`:
- Create task functions in `apps/dashboard/tasks.py`
- Use `EmailMultiAlternatives` + `render_to_string`
- Queue via `queue_task()` from `baky/tasks.py`
- Add `BAKY_ADMIN_EMAIL` setting to `baky/settings/base.py`

### Design Decisions (MVP Scope)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Yearly billing? | Out of scope | Onboarding only creates monthly; defer to v1.1 |
| Track request status? | No model | Fire-and-forget emails + flash messages for MVP |
| Owner confirmation email? | Yes | Trust-focused brand requires written confirmation |
| Extra inspection pricing? | Not shown | "Unser Team meldet sich bei Ihnen" |
| State transitions | Active→all actions; Paused→reactivate+cancel; Cancelled→contact support | Simplest UX mapping |
| Navigation placement | "Abonnement" sidebar item (replaces "Einstellungen") | Direct, discoverable |

## Acceptance Criteria

- [ ] Subscription overview page shows plan name, status, price, started date, next billing date, inspections used/limit
- [ ] Dashboard index shows subscription summary card (plan, status, inspections used)
- [ ] Plan change request form with plan selection sends email to admin + confirmation to owner
- [ ] Pause request form sends email to admin + confirmation to owner
- [ ] Cancel request form sends email to admin + confirmation to owner
- [ ] Extra inspection booking form (apartment, preferred date, notes) sends email to admin + confirmation to owner
- [ ] Billing history page shows empty state placeholder
- [ ] All views handle "no subscription" state gracefully (no 500 errors)
- [ ] All views require `@owner_required` and filter by `request.user`
- [ ] Sidebar "Abonnement" link is active; bottom nav updated
- [ ] German UI labels, mobile-first responsive design
- [ ] `make lint` and `make test` pass

## Implementation Tasks (TDD)

### Task 1: Add PLAN_PRICES and helper methods to Subscription model

**Files:** `apps/accounts/models.py`, `tests/accounts/test_models.py`

**Test first** (`tests/accounts/test_models.py`):
```python
@pytest.mark.django_db
class TestSubscriptionPricing:
    def test_get_monthly_price_basis(self):
        sub = SubscriptionFactory(plan=Subscription.Plan.BASIS)
        assert sub.get_monthly_price() == 89

    def test_get_monthly_price_standard(self):
        sub = SubscriptionFactory(plan=Subscription.Plan.STANDARD)
        assert sub.get_monthly_price() == 149

    def test_get_monthly_price_premium(self):
        sub = SubscriptionFactory(plan=Subscription.Plan.PREMIUM)
        assert sub.get_monthly_price() == 249

    def test_get_next_billing_date_monthly(self):
        sub = SubscriptionFactory(started_at=date(2026, 1, 15))
        # Today is 2026-04-02, so next billing is 2026-04-15
        assert sub.get_next_billing_date() == date(2026, 4, 15)

    def test_get_next_billing_date_month_end(self):
        sub = SubscriptionFactory(started_at=date(2026, 1, 31))
        # Next billing after 2026-04-02 should handle short months
        next_date = sub.get_next_billing_date()
        assert next_date.month >= 4

    def test_get_next_billing_date_paused_returns_none(self):
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        assert sub.get_next_billing_date() is None

    def test_get_next_billing_date_cancelled_returns_none(self):
        sub = SubscriptionFactory(status=Subscription.Status.CANCELLED)
        assert sub.get_next_billing_date() is None

    def test_get_inspections_used_this_month(self):
        sub = SubscriptionFactory()
        assert sub.get_inspections_used_this_month() == 0
```

**Implementation** (`apps/accounts/models.py`):
```python
PLAN_PRICES = {
    Plan.BASIS: 89,
    Plan.STANDARD: 149,
    Plan.PREMIUM: 249,
}

def get_monthly_price(self) -> int:
    return self.PLAN_PRICES.get(self.plan, 89)

def get_next_billing_date(self) -> date | None:
    if self.status != self.Status.ACTIVE:
        return None
    today = date.today()
    # Calculate next occurrence of billing day
    billing_day = min(self.started_at.day, 28)  # Clamp to 28 for safety
    candidate = today.replace(day=billing_day)
    if candidate <= today:
        # Move to next month
        if today.month == 12:
            candidate = candidate.replace(year=today.year + 1, month=1)
        else:
            candidate = candidate.replace(month=today.month + 1)
    return candidate

def get_inspections_used_this_month(self) -> int:
    from apps.inspections.models import Inspection
    today = date.today()
    return Inspection.objects.filter(
        apartment__owner=self.owner,
        status=Inspection.Status.COMPLETED,
        completed_at__year=today.year,
        completed_at__month=today.month,
    ).count()
```

**Verify:** `make test ARGS="-k TestSubscriptionPricing"`

---

### Task 2: Add BAKY_ADMIN_EMAIL setting

**Files:** `baky/settings/base.py`

**Implementation:**
```python
# Admin notifications
BAKY_ADMIN_EMAIL = env("BAKY_ADMIN_EMAIL", default="admin@baky.at")
```

**Verify:** `make manage CMD="shell -c \"from django.conf import settings; print(settings.BAKY_ADMIN_EMAIL)\""`

---

### Task 3: Create subscription forms

**Files:** `apps/dashboard/forms.py`, `tests/dashboard/test_forms.py`

**Test first** (`tests/dashboard/test_forms.py`):
```python
@pytest.mark.django_db
class TestPlanChangeRequestForm:
    def test_valid_plan_change(self):
        form = PlanChangeRequestForm(data={"requested_plan": "premium", "message": "Upgrade bitte"})
        assert form.is_valid()

    def test_plan_required(self):
        form = PlanChangeRequestForm(data={"requested_plan": "", "message": ""})
        assert not form.is_valid()

    def test_message_optional(self):
        form = PlanChangeRequestForm(data={"requested_plan": "standard"})
        assert form.is_valid()

class TestSubscriptionActionForm:
    def test_valid_with_reason(self):
        form = SubscriptionActionForm(data={"reason": "Urlaub"})
        assert form.is_valid()

    def test_valid_without_reason(self):
        form = SubscriptionActionForm(data={})
        assert form.is_valid()

class TestExtraInspectionForm:
    def test_valid_form(self, apartment):
        form = ExtraInspectionForm(
            data={"apartment": apartment.pk, "preferred_date": "2026-04-15", "notes": "Dringend"},
            owner=apartment.owner,
        )
        assert form.is_valid()

    def test_apartment_required(self):
        owner = OwnerFactory()
        form = ExtraInspectionForm(data={"preferred_date": "2026-04-15"}, owner=owner)
        assert not form.is_valid()

    def test_only_own_apartments(self, apartment):
        other_owner = OwnerFactory()
        form = ExtraInspectionForm(
            data={"apartment": apartment.pk, "preferred_date": "2026-04-15"},
            owner=other_owner,
        )
        assert not form.is_valid()
```

**Implementation** (`apps/dashboard/forms.py`):
- `PlanChangeRequestForm` — ChoiceField for plan (basis/standard/premium), optional message TextField
- `SubscriptionActionForm` — optional reason TextField (for pause/cancel)
- `ExtraInspectionForm` — apartment ModelChoiceField (filtered by owner), date field, optional notes

**Verify:** `make test ARGS="-k 'TestPlanChangeRequestForm or TestSubscriptionActionForm or TestExtraInspectionForm'"`

---

### Task 4: Create admin notification email templates and task functions

**Files:**
- `templates/emails/admin_plan_change.html`, `templates/emails/admin_plan_change.txt`
- `templates/emails/admin_subscription_action.html`, `templates/emails/admin_subscription_action.txt`
- `templates/emails/admin_extra_inspection.html`, `templates/emails/admin_extra_inspection.txt`
- `templates/emails/owner_request_confirmation.html`, `templates/emails/owner_request_confirmation.txt`
- `apps/dashboard/tasks.py`
- `tests/dashboard/test_tasks.py`

**Test first** (`tests/dashboard/test_tasks.py`):
```python
@pytest.mark.django_db
class TestAdminNotificationTasks:
    def test_send_plan_change_notification(self, subscription, mailoutbox):
        send_plan_change_notification(subscription.owner.pk, "premium", "Upgrade bitte")
        assert len(mailoutbox) == 2  # admin + owner confirmation
        assert "Planänderung" in mailoutbox[0].subject

    def test_send_pause_notification(self, subscription, mailoutbox):
        send_subscription_action_notification(subscription.owner.pk, "pause", "Urlaub")
        assert len(mailoutbox) == 2

    def test_send_cancel_notification(self, subscription, mailoutbox):
        send_subscription_action_notification(subscription.owner.pk, "cancel", "")
        assert len(mailoutbox) == 2

    def test_send_extra_inspection_notification(self, subscription, apartment, mailoutbox):
        send_extra_inspection_notification(subscription.owner.pk, apartment.pk, "2026-04-15", "Dringend")
        assert len(mailoutbox) == 2
```

**Implementation** (`apps/dashboard/tasks.py`):
- `send_plan_change_notification(owner_id, requested_plan, message)` — sends to admin + owner
- `send_subscription_action_notification(owner_id, action, reason)` — sends to admin + owner
- `send_extra_inspection_notification(owner_id, apartment_id, preferred_date, notes)` — sends to admin + owner

All follow the `EmailMultiAlternatives` pattern from `apps/reports/tasks.py`.

**Verify:** `make test ARGS="-k TestAdminNotificationTasks"`

---

### Task 5: Create subscription views

**Files:** `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `tests/dashboard/test_subscription_views.py`

**Test first** (`tests/dashboard/test_subscription_views.py`):
```python
@pytest.mark.django_db
class TestSubscriptionOverview:
    def test_requires_login(self, client):
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 302

    def test_requires_owner_role(self, client, inspector):
        client.force_login(inspector)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 404

    def test_active_subscription(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        assert "Basis" in response.content.decode()

    def test_no_subscription(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        assert "Kein Abonnement" in response.content.decode()

    def test_paused_subscription(self, client):
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        assert "Pausiert" in response.content.decode()

    def test_cancelled_subscription(self, client):
        sub = SubscriptionFactory(status=Subscription.Status.CANCELLED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription"))
        assert response.status_code == 200
        assert "Gekündigt" in response.content.decode()

@pytest.mark.django_db
class TestPlanChangeRequest:
    def test_requires_login(self, client):
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 302

    def test_get_shows_form(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 200

    def test_post_valid_sends_notification(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.post(reverse("dashboard:subscription_change"), {
            "requested_plan": "premium", "message": "Upgrade bitte"
        })
        assert response.status_code == 302  # redirect to subscription overview

    def test_no_subscription_redirects(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 302

    def test_paused_subscription_blocked(self, client):
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_change"))
        assert response.status_code == 302

@pytest.mark.django_db
class TestPauseRequest:
    def test_get_shows_form(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:subscription_pause"))
        assert response.status_code == 200

    def test_post_sends_notification(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.post(reverse("dashboard:subscription_pause"), {"reason": "Urlaub"})
        assert response.status_code == 302

    def test_already_paused_blocked(self, client):
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_pause"))
        assert response.status_code == 302

@pytest.mark.django_db
class TestCancelRequest:
    def test_get_shows_form(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:subscription_cancel"))
        assert response.status_code == 200

    def test_post_sends_notification(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.post(reverse("dashboard:subscription_cancel"), {})
        assert response.status_code == 302

    def test_already_cancelled_blocked(self, client):
        sub = SubscriptionFactory(status=Subscription.Status.CANCELLED)
        client.force_login(sub.owner)
        response = client.get(reverse("dashboard:subscription_cancel"))
        assert response.status_code == 302

@pytest.mark.django_db
class TestExtraInspectionBooking:
    def test_get_shows_form(self, client, subscription, apartment):
        apartment.owner = subscription.owner
        apartment.save()
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:subscription_extra"))
        assert response.status_code == 200

    def test_post_sends_notification(self, client, subscription, apartment):
        apartment.owner = subscription.owner
        apartment.save()
        client.force_login(subscription.owner)
        response = client.post(reverse("dashboard:subscription_extra"), {
            "apartment": apartment.pk, "preferred_date": "2026-04-15", "notes": "Dringend"
        })
        assert response.status_code == 302

    def test_no_subscription_blocked(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:subscription_extra"))
        assert response.status_code == 302

@pytest.mark.django_db
class TestBillingHistory:
    def test_requires_login(self, client):
        response = client.get(reverse("dashboard:subscription_billing"))
        assert response.status_code == 302

    def test_shows_empty_state(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:subscription_billing"))
        assert response.status_code == 200

@pytest.mark.django_db
class TestDashboardIndexSubscriptionCard:
    def test_index_shows_subscription_card(self, client, subscription):
        client.force_login(subscription.owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert "Basis" in response.content.decode()

    def test_index_no_subscription_shows_cta(self, client):
        owner = OwnerFactory()
        client.force_login(owner)
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
```

**URL patterns** (`apps/dashboard/urls.py`):
```python
path("subscription/", views.subscription_overview, name="subscription"),
path("subscription/change/", views.subscription_change, name="subscription_change"),
path("subscription/pause/", views.subscription_pause, name="subscription_pause"),
path("subscription/cancel/", views.subscription_cancel, name="subscription_cancel"),
path("subscription/extra/", views.subscription_extra, name="subscription_extra"),
path("subscription/billing/", views.subscription_billing, name="subscription_billing"),
```

**Views** (`apps/dashboard/views.py`):
- All decorated with `@owner_required`
- Use `hasattr(request.user, 'subscription')` try/except guard for OneToOneField
- Helper: `_get_subscription_or_none(user)` returns subscription or None
- GET renders form; POST validates form, queues notification task, redirects with success message
- Blocked states redirect with warning message

**Verify:** `make test ARGS="-k 'TestSubscription or TestDashboardIndexSubscription'"`

---

### Task 6: Create subscription templates

**Files:**
- `templates/dashboard/subscription.html` — overview page
- `templates/dashboard/subscription_change.html` — plan change form
- `templates/dashboard/subscription_pause.html` — pause request form
- `templates/dashboard/subscription_cancel.html` — cancel request form
- `templates/dashboard/subscription_extra.html` — extra inspection form
- `templates/dashboard/subscription_billing.html` — billing history placeholder
- `templates/dashboard/_subscription_card.html` — summary card for dashboard index

**Design specs (from CLAUDE.md design context):**

- Extend `dashboard/base_dashboard.html`
- Set `active` context to `"subscription"` for sidebar highlighting
- Mobile-first: single-column at 375px, two-column cards at md+
- Use existing components: `_card.html`, `_alert.html`, `_modal.html` (confirmation dialogs for pause/cancel)
- Color tokens: `emerald-500` for active status, `amber-500` for paused, `rose-500` for cancelled
- Plan comparison cards in change form with current plan highlighted
- Large tap targets for mobile (min 44px)
- German labels throughout

**Subscription overview layout:**
```
┌─────────────────────────────────────┐
│ Ihr Abonnement                      │
├─────────────────────────────────────┤
│ Plan: Basis          Status: Aktiv  │
│ Preis: €89/Monat                    │
│ Seit: 15.01.2026                    │
│ Nächste Abrechnung: 15.04.2026     │
│ Inspektionen: 1/2 diesen Monat     │
├─────────────────────────────────────┤
│ [Plan ändern] [Pausieren] [Kündigen]│
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ Zusätzliche Inspektion buchen       │
│ [Inspektion buchen →]               │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ Rechnungen                          │
│ [Rechnungshistorie →]               │
└─────────────────────────────────────┘
```

**Verify:** Visual check at `http://localhost:8010/dashboard/subscription/`

---

### Task 7: Update sidebar and bottom navigation

**Files:**
- `templates/components/_sidebar.html`
- `templates/components/_owner_bottom_nav.html`

**Implementation:**
- Replace disabled "Einstellungen" `<span>` with active `<a>` linking to `{% url 'dashboard:subscription' %}`
- Change label to "Abonnement" with a credit-card or subscription icon
- Add `active == 'subscription'` highlight logic (matches existing pattern)
- In bottom nav, replace disabled "Profil" with "Abonnement" link

**Verify:** Visual check — sidebar link is clickable and highlights when on subscription pages

---

### Task 8: Update dashboard index to show subscription card

**Files:** `apps/dashboard/views.py` (index view), `templates/dashboard/index.html`

**Implementation:**
- In `index` view, add subscription context:
  ```python
  try:
      subscription = request.user.subscription
      has_subscription = True
  except Subscription.DoesNotExist:
      subscription = None
      has_subscription = False
  ```
- Pass `subscription` and `has_subscription` to template context
- In `index.html`, add `{% include "dashboard/_subscription_card.html" %}` above apartment grid
- Card shows: plan name, status badge, inspections used/limit
- If no subscription: show "Kein aktives Abonnement" with link to support

**Verify:** `make test ARGS="-k TestDashboardIndexSubscription"`

## Success Metrics

- All 6 subscription pages render without errors for all subscription states (active, paused, cancelled, none)
- Email notifications arrive in Mailpit during local dev
- All forms validate correctly and show German error messages
- Mobile layout works at 375px (tap targets >= 44px, no horizontal scroll)

## Dependencies

- `apps/accounts/models.py` — Subscription model (exists, needs helper methods)
- `apps/dashboard/` — dashboard app (exists, adding views/forms/templates)
- `baky/tasks.py` — queue_task helper (exists)
- `templates/emails/_base.html` — email base template (exists)

## Sources

- Issue: #18
- Subscription model: `apps/accounts/models.py:39`
- Dashboard views: `apps/dashboard/views.py`
- Dashboard URLs: `apps/dashboard/urls.py`
- Email pattern: `apps/reports/tasks.py`, `apps/inspections/tasks.py`
- OneToOneField guard: `docs/solutions/runtime-errors/django-reverse-onetoone-relatedobjectdoesnotexist-in-templates.md`
- Template comment safety: `docs/solutions/runtime-errors/django-template-tags-in-html-comments-recursion.md`
- Pricing tiers: `templates/public/pricing.html`, `apps/accounts/forms.py:167`
