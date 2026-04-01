import logging

logger = logging.getLogger(__name__)


def generate_report(inspection_id: int) -> dict:
    """Generate a report from a completed inspection.

    Called as a background task after an inspection is submitted.
    Returns a dict with the report ID and status for task result tracking.
    """
    from apps.inspections.models import Inspection

    inspection = Inspection.objects.select_related("apartment", "inspector").get(pk=inspection_id)

    if inspection.status != Inspection.Status.COMPLETED:
        logger.warning("Skipping report generation for inspection %d — status is %s", inspection_id, inspection.status)
        return {"inspection_id": inspection_id, "status": "skipped", "reason": "not_completed"}

    # Report generation logic will be implemented in the reports feature (#23).
    # For now, this task validates the inspection exists and is in the correct state.
    logger.info("Report generation queued for inspection %d (%s)", inspection_id, inspection.apartment.address)
    return {"inspection_id": inspection_id, "status": "pending_implementation"}


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
