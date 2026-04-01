import logging
from collections import OrderedDict

from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_report(inspection_id: int) -> dict:
    """Generate a report from a completed inspection.

    Called as a background task after an inspection is submitted.
    Returns a dict with the report ID and status for task result tracking.
    """
    from apps.inspections.models import Inspection
    from apps.reports.models import Report

    inspection = (
        Inspection.objects.select_related("apartment", "apartment__owner", "inspector")
        .prefetch_related("items", "photos")
        .get(pk=inspection_id)
    )

    if inspection.status != Inspection.Status.COMPLETED:
        logger.warning("Skipping report generation for inspection %d — status is %s", inspection_id, inspection.status)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "not_completed"}

    # Idempotency: get existing or create new report
    report, created = Report.objects.get_or_create(
        inspection=inspection,
        defaults={"status": Report.Status.GENERATING},
    )

    if not created and report.status == Report.Status.COMPLETED:
        logger.info("Report %d already completed for inspection %d — skipping", report.pk, inspection_id)
        return {
            "report_id": report.pk,
            "inspection_id": inspection_id,
            "status": "skipped",
            "reason": "already_completed",
        }

    # Mark as generating (handles retry of failed/pending reports)
    report.status = Report.Status.GENERATING
    report.error_message = ""
    report.save(update_fields=["status", "error_message", "updated_at"])

    try:
        html_content = _render_report_html(inspection)
    except Exception as e:
        logger.exception("Report generation failed for inspection %d", inspection_id)
        report.status = Report.Status.FAILED
        report.error_message = str(e)
        report.save(update_fields=["status", "error_message", "updated_at"])
        return {"report_id": report.pk, "inspection_id": inspection_id, "status": "failed"}

    report.html_content = html_content
    report.status = Report.Status.COMPLETED
    report.generated_at = timezone.now()
    report.save(update_fields=["html_content", "status", "generated_at", "updated_at"])

    logger.info("Report %d generated for inspection %d (%s)", report.pk, inspection_id, inspection.apartment.address)
    return {"report_id": report.pk, "inspection_id": inspection_id, "status": "completed"}


def _render_report_html(inspection) -> str:
    """Render the inspection data into a standalone HTML report."""
    items = list(inspection.items.all())
    photos = list(inspection.photos.all())

    # Group items by category, ordered by first appearance (min order)
    categories = OrderedDict()
    for item in sorted(items, key=lambda i: i.order):
        if item.category not in categories:
            categories[item.category] = []
        categories[item.category].append(item)

    # Build photo lookup: item_id -> [photos]
    item_photos = {}
    general_photos = []
    for photo in photos:
        if photo.inspection_item_id:
            item_photos.setdefault(photo.inspection_item_id, []).append(photo)
        else:
            general_photos.append(photo)

    # Calculate duration
    duration = _calculate_duration(inspection)

    context = {
        "inspection": inspection,
        "apartment": inspection.apartment,
        "inspector": inspection.inspector,
        "categories": categories,
        "item_photos": item_photos,
        "all_photos": photos,
        "general_photos": general_photos,
        "duration": duration,
        "generated_at": timezone.now(),
    }

    return render_to_string("reports/report.html", context)


def _calculate_duration(inspection) -> str | None:
    """Calculate inspection duration as a human-readable string."""
    start = inspection.started_at or inspection.scheduled_at
    end = inspection.completed_at
    if not start or not end:
        return None
    delta = end - start
    total_minutes = int(delta.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0:
        return f"{hours} Std. {minutes} Min."
    return f"{minutes} Min."


def send_report_email(inspection_id: int) -> dict:
    """Send the generated report to the apartment owner via email.

    Called after report generation succeeds.
    """
    from apps.inspections.models import Inspection

    inspection = Inspection.objects.select_related("apartment__owner").get(pk=inspection_id)
    owner = inspection.apartment.owner

    logger.info("Report email queued for owner %s (inspection %d)", owner.email, inspection_id)
    # Email dispatch logic will be implemented in #24.
    return {"inspection_id": inspection_id, "owner_email": owner.email, "status": "pending_implementation"}
