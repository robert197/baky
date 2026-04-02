import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.accounts.models import User

logger = logging.getLogger(__name__)

ACTION_LABELS = {
    "pause": "Pausierung",
    "cancel": "Kündigung",
}


def send_plan_change_notification(owner_id: int, requested_plan: str, message: str) -> None:
    """Send plan change request notification to admin and confirmation to owner."""
    owner = User.objects.get(pk=owner_id)
    subscription = owner.subscription

    context = {
        "owner": owner,
        "subscription": subscription,
        "requested_plan": requested_plan,
        "message": message,
    }

    # Admin notification
    subject = f"Planänderung angefragt — {owner.get_full_name() or owner.username}"
    _send_email(subject, "emails/admin_plan_change", context, [settings.BAKY_ADMIN_EMAIL])

    # Owner confirmation
    _send_email(
        "Bestätigung: Ihre Planänderung wurde angefragt",
        "emails/owner_request_confirmation",
        {**context, "request_type": "Planänderung", "detail": f"Gewünschter Plan: {requested_plan.title()}"},
        [owner.email],
    )


def send_subscription_action_notification(owner_id: int, action: str, reason: str) -> None:
    """Send pause/cancel request notification to admin and confirmation to owner."""
    if action not in ACTION_LABELS:
        raise ValueError(f"Invalid subscription action: {action}")
    owner = User.objects.get(pk=owner_id)
    subscription = owner.subscription
    action_label = ACTION_LABELS[action]

    context = {
        "owner": owner,
        "subscription": subscription,
        "action": action,
        "action_label": action_label,
        "reason": reason,
    }

    subject = f"{action_label} angefragt — {owner.get_full_name() or owner.username}"
    _send_email(subject, "emails/admin_subscription_action", context, [settings.BAKY_ADMIN_EMAIL])

    _send_email(
        f"Bestätigung: Ihre {action_label} wurde angefragt",
        "emails/owner_request_confirmation",
        {**context, "request_type": action_label, "detail": f"Grund: {reason}" if reason else ""},
        [owner.email],
    )


def send_extra_inspection_notification(owner_id: int, apartment_id: int, preferred_date: str, notes: str) -> None:
    """Send extra inspection booking notification to admin and confirmation to owner."""
    from apps.apartments.models import Apartment

    owner = User.objects.get(pk=owner_id)
    apartment = Apartment.objects.get(pk=apartment_id, owner=owner)

    context = {
        "owner": owner,
        "apartment": apartment,
        "preferred_date": preferred_date,
        "notes": notes,
    }

    subject = f"Zusätzliche Inspektion angefragt — {apartment.address}"
    _send_email(subject, "emails/admin_extra_inspection", context, [settings.BAKY_ADMIN_EMAIL])

    _send_email(
        "Bestätigung: Ihre Inspektionsanfrage wurde gesendet",
        "emails/owner_request_confirmation",
        {
            **context,
            "request_type": "Zusätzliche Inspektion",
            "detail": f"Wohnung: {apartment.address}, Datum: {preferred_date}",
        },
        [owner.email],
    )


def _send_email(subject: str, template_prefix: str, context: dict, to: list[str]) -> None:
    """Send an email using HTML and text templates."""
    html_body = render_to_string(f"{template_prefix}.html", context)
    text_body = render_to_string(f"{template_prefix}.txt", context)
    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, to)
    msg.attach_alternative(html_body, "text/html")
    msg.send()
