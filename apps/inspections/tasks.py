import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_thumbnail(photo_id: int) -> dict:
    """Generate a thumbnail for an uploaded inspection photo.

    Photo.save() auto-generates thumbnails on first save. This task exists for
    re-generating thumbnails (e.g., after a resize config change) or for photos
    created via bulk import that bypass the save hook.
    """
    from apps.inspections.models import Photo
    from baky.storage import create_thumbnail

    photo = Photo.objects.get(pk=photo_id)

    if photo.thumbnail:
        logger.info("Photo %d already has a thumbnail, skipping", photo_id)
        return {"photo_id": photo_id, "status": "already_exists"}

    photo.file.seek(0)
    photo.thumbnail = create_thumbnail(photo.file)
    photo.save(update_fields=["thumbnail"])

    logger.info("Thumbnail generated for photo %d", photo_id)
    return {"photo_id": photo_id, "status": "created"}


def send_inspection_reminder(inspection_id: int) -> dict:
    """Send a reminder to an inspector about an upcoming inspection.

    Scheduled to run before the inspection's scheduled_at time.
    """
    from apps.inspections.models import Inspection

    inspection = Inspection.objects.select_related("inspector", "apartment").get(pk=inspection_id)

    if inspection.status != Inspection.Status.SCHEDULED:
        logger.info("Inspection %d is no longer scheduled (%s), skipping reminder", inspection_id, inspection.status)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": inspection.status}

    if inspection.scheduled_at < timezone.now():
        logger.warning("Inspection %d scheduled_at is in the past, skipping reminder", inspection_id)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "past_due"}

    if not inspection.inspector:
        logger.info("Inspection %d has no inspector assigned, skipping reminder", inspection_id)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "no_inspector"}

    subject = f"BAKY Inspektion morgen — {inspection.apartment.address}"
    scheduled_date = timezone.localtime(inspection.scheduled_at).strftime("%d.%m.%Y")
    scheduled_time = timezone.localtime(inspection.scheduled_at).strftime("%H:%M")

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

    logger.info(
        "Reminder sent to %s for inspection %d at %s",
        inspection.inspector.email,
        inspection_id,
        inspection.apartment.address,
    )
    return {"inspection_id": inspection_id, "inspector_email": inspection.inspector.email, "status": "sent"}


def send_urgent_notification(inspection_id: int) -> dict:
    """Send an immediate notification to the owner when an inspection is rated URGENT.

    Triggered at submission time for inspections with critical issues.
    """
    from apps.inspections.models import Inspection

    inspection = Inspection.objects.select_related("apartment", "apartment__owner", "inspector").get(pk=inspection_id)

    if inspection.status != Inspection.Status.COMPLETED:
        logger.warning(
            "Skipping urgent notification for inspection %d — status is %s", inspection_id, inspection.status
        )
        return {"inspection_id": inspection_id, "status": "skipped", "reason": inspection.status}

    if inspection.overall_rating != Inspection.OverallRating.URGENT:
        logger.info(
            "Skipping urgent notification for inspection %d — rating is %s", inspection_id, inspection.overall_rating
        )
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "not_urgent"}

    owner = inspection.apartment.owner
    flagged_items = list(inspection.items.exclude(result="ok").exclude(result="na"))
    report_url = f"{settings.SITE_URL}/reports/{inspection.pk}/"

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

    logger.info(
        "URGENT notification sent to %s for inspection %d at %s",
        owner.email,
        inspection_id,
        inspection.apartment.address,
    )
    return {"inspection_id": inspection_id, "owner_email": owner.email, "status": "sent"}


def send_owner_reminder(inspection_id: int) -> dict:
    """Send a day-before reminder to the apartment owner.

    Message: "Inspektion morgen geplant" with inspection details.
    """
    from apps.inspections.models import Inspection

    inspection = Inspection.objects.select_related("apartment", "apartment__owner").get(pk=inspection_id)

    if inspection.status != Inspection.Status.SCHEDULED:
        logger.info(
            "Inspection %d is no longer scheduled (%s), skipping owner reminder", inspection_id, inspection.status
        )
        return {"inspection_id": inspection_id, "status": "skipped", "reason": inspection.status}

    owner = inspection.apartment.owner
    subject = f"BAKY Inspektion morgen — {inspection.apartment.address}"
    scheduled_date = timezone.localtime(inspection.scheduled_at).strftime("%d.%m.%Y")
    scheduled_time = timezone.localtime(inspection.scheduled_at).strftime("%H:%M")

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

    logger.info(
        "Owner reminder sent to %s for inspection %d at %s on %s",
        owner.email,
        inspection_id,
        inspection.apartment.address,
        inspection.scheduled_at.strftime("%d.%m.%Y %H:%M"),
    )
    return {"inspection_id": inspection_id, "owner_email": owner.email, "status": "sent"}
