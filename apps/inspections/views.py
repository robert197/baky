import logging
from collections import OrderedDict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import inspector_required
from baky.tasks import queue_task

from .models import Inspection, InspectionItem, Photo

logger = logging.getLogger(__name__)


@inspector_required
def index(request):
    """Inspector landing page — redirect to schedule."""
    return schedule(request)


@inspector_required
def schedule(request):
    """Show upcoming inspections for the logged-in inspector."""
    today = timezone.localtime(timezone.now()).date()
    inspections = list(
        Inspection.objects.filter(
            inspector=request.user,
            status__in=[Inspection.Status.SCHEDULED, Inspection.Status.IN_PROGRESS],
            scheduled_at__date__gte=today,
        )
        .select_related("apartment", "apartment__owner")
        .order_by("scheduled_at")
    )

    # Collect apartment IDs to batch-fetch previous inspections
    apartment_ids = [i.apartment_id for i in inspections]

    # Get the most recent completed inspection per apartment using DISTINCT ON (PostgreSQL)
    previous_inspections = {}
    if apartment_ids:
        prev_qs = (
            Inspection.objects.filter(
                apartment_id__in=apartment_ids,
                status=Inspection.Status.COMPLETED,
                completed_at__isnull=False,
            )
            .order_by("apartment_id", "-completed_at")
            .distinct("apartment_id")
        )
        for prev in prev_qs:
            prev.flagged_labels = []
            previous_inspections[prev.apartment_id] = prev

        # Fetch flagged items for previous inspections
        prev_ids = [p.pk for p in previous_inspections.values()]
        if prev_ids:
            flagged_items = InspectionItem.objects.filter(
                inspection_id__in=prev_ids,
                result=InspectionItem.Result.FLAGGED,
            ).values_list("inspection_id", "checklist_label")
            flagged_by_inspection = {}
            for insp_id, label in flagged_items:
                flagged_by_inspection.setdefault(insp_id, []).append(label)

            for prev in previous_inspections.values():
                prev.flagged_labels = flagged_by_inspection.get(prev.pk, [])

    # Annotate each inspection with its previous inspection context
    for inspection in inspections:
        inspection.previous_inspection = previous_inspections.get(inspection.apartment_id)

    # Group by date for display
    grouped = {}
    for inspection in inspections:
        date = timezone.localtime(inspection.scheduled_at).date()
        grouped.setdefault(date, []).append(inspection)

    return render(
        request,
        "inspector/schedule.html",
        {
            "grouped_inspections": grouped,
            "today": today,
            "active": "schedule",
        },
    )


@inspector_required
def access_details(request, inspection_id):
    """HTMX endpoint: return access details for an inspection (security: only assigned inspector)."""
    inspection = get_object_or_404(
        Inspection.objects.select_related("apartment"),
        pk=inspection_id,
    )
    if inspection.inspector_id != request.user.id:
        raise Http404
    return render(request, "inspector/_access_details.html", {"inspection": inspection})


def _get_inspection_for_inspector(request, inspection_id, allowed_statuses=None):
    """Fetch an inspection, ensuring it belongs to the requesting inspector."""
    inspection = get_object_or_404(
        Inspection.objects.select_related("apartment", "apartment__owner"),
        pk=inspection_id,
    )
    if inspection.inspector_id != request.user.id:
        raise Http404
    if allowed_statuses and inspection.status not in allowed_statuses:
        raise Http404
    return inspection


@inspector_required
@require_POST
def start_inspection(request, inspection_id):
    """Start an inspection: create items from checklist template, set status to IN_PROGRESS."""
    inspection = _get_inspection_for_inspector(request, inspection_id)

    # If already in progress, just redirect to execute
    if inspection.status == Inspection.Status.IN_PROGRESS:
        return redirect("inspections:execute_inspection", inspection_id=inspection.pk)

    if inspection.status != Inspection.Status.SCHEDULED:
        raise Http404

    # Create InspectionItems from the apartment's checklist template
    if not hasattr(inspection.apartment, "checklist_template"):
        raise Http404
    template = inspection.apartment.checklist_template

    items_to_create = [
        InspectionItem(
            inspection=inspection,
            checklist_label=item_data["label"],
            category=item_data["category"],
            order=item_data["order"],
            result=InspectionItem.Result.OK,
            severity=InspectionItem.Severity.NONE,
        )
        for item_data in template.items
    ]
    InspectionItem.objects.bulk_create(items_to_create)

    # Update inspection status
    inspection.status = Inspection.Status.IN_PROGRESS
    inspection.started_at = timezone.now()
    inspection.save(update_fields=["status", "started_at", "updated_at"])

    return redirect("inspections:execute_inspection", inspection_id=inspection.pk)


@inspector_required
def execute_inspection(request, inspection_id):
    """Display the checklist execution interface for an in-progress inspection."""
    inspection = _get_inspection_for_inspector(
        request,
        inspection_id,
        allowed_statuses=[Inspection.Status.IN_PROGRESS],
    )

    items = inspection.items.order_by("order")

    # Prefetch photos for all items
    photos_by_item = {}
    all_photos = Photo.objects.filter(inspection=inspection).order_by("-created_at")
    general_photos = []
    for photo in all_photos:
        if photo.inspection_item_id:
            photos_by_item.setdefault(photo.inspection_item_id, []).append(photo)
        else:
            general_photos.append(photo)

    # Group items by category, preserving order
    grouped_items = OrderedDict()
    for item in items:
        item.photos_list = photos_by_item.get(item.pk, [])
        grouped_items.setdefault(item.category, []).append(item)

    total = items.count()

    return render(
        request,
        "inspector/execute.html",
        {
            "inspection": inspection,
            "grouped_items": grouped_items,
            "total_items": total,
            "general_photos": general_photos,
            "active": "schedule",
        },
    )


@inspector_required
@require_POST
def update_item(request, item_id):
    """HTMX endpoint: update a single checklist item's result, severity, and notes."""
    item = get_object_or_404(
        InspectionItem.objects.select_related("inspection", "inspection__apartment"),
        pk=item_id,
    )
    if item.inspection.inspector_id != request.user.id:
        raise Http404
    if item.inspection.status != Inspection.Status.IN_PROGRESS:
        raise Http404

    result = request.POST.get("result", "")
    valid_results = [r[0] for r in InspectionItem.Result.choices]
    if result not in valid_results:
        return HttpResponseBadRequest("Invalid result value.")

    item.result = result

    if result == InspectionItem.Result.FLAGGED:
        severity = request.POST.get("severity", InspectionItem.Severity.LOW)
        valid_severities = [s[0] for s in InspectionItem.Severity.choices]
        if severity in valid_severities:
            item.severity = severity
        else:
            item.severity = InspectionItem.Severity.LOW
        item.notes = request.POST.get("notes", "")
    else:
        # Clear severity and notes when not flagged
        item.severity = InspectionItem.Severity.NONE
        item.notes = ""

    item.save(update_fields=["result", "severity", "notes"])

    return render(request, "inspector/_checklist_item.html", {"item": item})


@inspector_required
@require_POST
def update_general_notes(request, inspection_id):
    """HTMX endpoint: update general notes for an inspection."""
    inspection = _get_inspection_for_inspector(
        request,
        inspection_id,
        allowed_statuses=[Inspection.Status.IN_PROGRESS],
    )
    inspection.general_notes = request.POST.get("general_notes", "")
    inspection.save(update_fields=["general_notes", "updated_at"])

    return render(
        request,
        "inspector/_general_notes.html",
        {"inspection": inspection, "saved": True},
    )


# --- Photo views ---


def _get_photo_for_inspector(request, photo_id):
    """Fetch a photo, ensuring it belongs to an in-progress inspection assigned to the requesting inspector."""
    photo = get_object_or_404(
        Photo.objects.select_related("inspection"),
        pk=photo_id,
    )
    if photo.inspection.inspector_id != request.user.id:
        raise Http404
    if photo.inspection.status != Inspection.Status.IN_PROGRESS:
        raise Http404
    return photo


@inspector_required
@require_POST
def upload_photo(request, inspection_id):
    """HTMX endpoint: upload a photo for an inspection (general or item-specific)."""
    inspection = _get_inspection_for_inspector(
        request,
        inspection_id,
        allowed_statuses=[Inspection.Status.IN_PROGRESS],
    )

    file = request.FILES.get("file")
    if not file:
        return HttpResponseBadRequest("Keine Datei hochgeladen.")

    item_id = request.POST.get("item_id")
    inspection_item = None
    if item_id:
        try:
            inspection_item = InspectionItem.objects.get(pk=item_id, inspection=inspection)
        except InspectionItem.DoesNotExist:
            return HttpResponseBadRequest("Ungültiger Checklistenpunkt.")

    caption = request.POST.get("caption", "")[:255]

    photo = Photo(
        inspection=inspection,
        inspection_item=inspection_item,
        file=file,
        caption=caption,
    )
    try:
        photo.full_clean()
    except ValidationError as e:
        return HttpResponseBadRequest(str(e))
    photo.save()

    return render(request, "inspector/_photo_thumbnail.html", {"photo": photo, "inspection": inspection})


@inspector_required
@require_POST
def delete_photo(request, photo_id):
    """HTMX endpoint: delete a photo and its files from storage."""
    photo = _get_photo_for_inspector(request, photo_id)
    # Delete files from storage before deleting the record
    if photo.file:
        photo.file.delete(save=False)
    if photo.thumbnail:
        photo.thumbnail.delete(save=False)
    photo.delete()
    return HttpResponse("")


@inspector_required
@require_POST
def update_photo_caption(request, photo_id):
    """HTMX endpoint: update a photo's caption."""
    photo = _get_photo_for_inspector(request, photo_id)
    photo.caption = request.POST.get("caption", "")[:255]
    photo.save(update_fields=["caption"])
    return render(request, "inspector/_photo_thumbnail.html", {"photo": photo, "inspection": photo.inspection})


# --- Submission flow ---


@inspector_required
def review_inspection(request, inspection_id):
    """Pre-submit review screen showing inspection summary."""
    inspection = _get_inspection_for_inspector(
        request,
        inspection_id,
        allowed_statuses=[Inspection.Status.IN_PROGRESS],
    )

    items = inspection.items.order_by("order")
    ok_count = items.filter(result=InspectionItem.Result.OK).count()
    flagged_count = items.filter(result=InspectionItem.Result.FLAGGED).count()
    na_count = items.filter(result=InspectionItem.Result.NA).count()
    flagged_items = items.filter(result=InspectionItem.Result.FLAGGED).order_by("order")
    photo_count = inspection.photos.count()

    return render(
        request,
        "inspector/review.html",
        {
            "inspection": inspection,
            "ok_count": ok_count,
            "flagged_count": flagged_count,
            "na_count": na_count,
            "total_items": ok_count + flagged_count + na_count,
            "flagged_items": flagged_items,
            "photo_count": photo_count,
            "rating_choices": Inspection.OverallRating.choices,
            "active": "schedule",
        },
    )


@inspector_required
@require_POST
def submit_inspection(request, inspection_id):
    """Submit a completed inspection — irreversible."""
    inspection = _get_inspection_for_inspector(
        request,
        inspection_id,
        allowed_statuses=[Inspection.Status.IN_PROGRESS],
    )

    # Validate overall rating is provided and valid
    overall_rating = request.POST.get("overall_rating", "")
    valid_ratings = [r[0] for r in Inspection.OverallRating.choices]
    if overall_rating not in valid_ratings:
        messages.error(request, "Bitte wählen Sie eine Gesamtbewertung aus.")
        return redirect("inspections:review_inspection", inspection_id=inspection.pk)

    # Validate at least one item exists
    if not inspection.items.exists():
        messages.error(request, "Inspektion hat keine Checklistenpunkte.")
        return redirect("inspections:review_inspection", inspection_id=inspection.pk)

    # Mark as completed
    inspection.status = Inspection.Status.COMPLETED
    inspection.completed_at = timezone.now()
    inspection.overall_rating = overall_rating
    inspection.save(update_fields=["status", "completed_at", "overall_rating", "updated_at"])

    # Trigger background tasks
    queue_task(
        "apps.reports.tasks.generate_report",
        inspection.pk,
        task_name=f"generate_report_{inspection.pk}",
    )
    queue_task(
        "apps.reports.tasks.send_report_email",
        inspection.pk,
        task_name=f"send_report_email_{inspection.pk}",
    )

    # Urgent rating triggers immediate notification
    if overall_rating == Inspection.OverallRating.URGENT:
        queue_task(
            "apps.inspections.tasks.send_urgent_notification",
            inspection.pk,
            task_name=f"urgent_notification_{inspection.pk}",
        )

    logger.info("Inspection %d submitted with rating=%s", inspection.pk, overall_rating)
    return redirect("inspections:inspection_submitted", inspection_id=inspection.pk)


@inspector_required
def inspection_submitted(request, inspection_id):
    """Post-submit confirmation screen."""
    inspection = _get_inspection_for_inspector(
        request,
        inspection_id,
        allowed_statuses=[Inspection.Status.COMPLETED],
    )

    items = inspection.items.order_by("order")
    ok_count = items.filter(result=InspectionItem.Result.OK).count()
    flagged_count = items.filter(result=InspectionItem.Result.FLAGGED).count()
    na_count = items.filter(result=InspectionItem.Result.NA).count()
    photo_count = inspection.photos.count()

    return render(
        request,
        "inspector/submitted.html",
        {
            "inspection": inspection,
            "ok_count": ok_count,
            "flagged_count": flagged_count,
            "na_count": na_count,
            "total_items": ok_count + flagged_count + na_count,
            "photo_count": photo_count,
            "active": "schedule",
        },
    )
