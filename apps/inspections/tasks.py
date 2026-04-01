import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_thumbnail(photo_id: int) -> dict:
    """Generate a thumbnail for an uploaded inspection photo.

    This offloads thumbnail creation to a background worker for large batches
    of photos uploaded during an inspection.
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

    logger.info(
        "Reminder sent to %s for inspection %d at %s",
        inspection.inspector.email,
        inspection_id,
        inspection.apartment.address,
    )
    # Actual notification logic will be implemented with email dispatch (#24).
    return {"inspection_id": inspection_id, "inspector_email": inspection.inspector.email, "status": "sent"}
