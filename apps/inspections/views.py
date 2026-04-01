from collections import OrderedDict

from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import inspector_required

from .models import Inspection, InspectionItem


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

    # Group items by category, preserving order
    grouped_items = OrderedDict()
    for item in items:
        grouped_items.setdefault(item.category, []).append(item)

    total = items.count()

    return render(
        request,
        "inspector/execute.html",
        {
            "inspection": inspection,
            "grouped_items": grouped_items,
            "total_items": total,
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

    result = request.POST.get("result", "")
    valid_results = [r[0] for r in InspectionItem.Result.choices]
    if result not in valid_results:
        return HttpResponseBadRequest("Invalid result value.")

    item.result = result

    if result == InspectionItem.Result.FLAGGED:
        severity = request.POST.get("severity", InspectionItem.Severity.NONE)
        valid_severities = [s[0] for s in InspectionItem.Severity.choices]
        if severity in valid_severities:
            item.severity = severity
        item.notes = request.POST.get("notes", "")
    else:
        # Clear severity and notes when not flagged
        item.severity = InspectionItem.Severity.NONE
        item.notes = ""

    item.save()

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
