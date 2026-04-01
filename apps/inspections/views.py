from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

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
    inspections = (
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

    # Get the most recent completed inspection per apartment (for previous context)
    previous_inspections = {}
    if apartment_ids:
        prev_qs = (
            Inspection.objects.filter(
                apartment_id__in=apartment_ids,
                status=Inspection.Status.COMPLETED,
            )
            .select_related("apartment")
            .order_by("apartment_id", "-completed_at")
        )
        for prev in prev_qs:
            if prev.apartment_id not in previous_inspections:
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
        prev = previous_inspections.get(inspection.apartment_id)
        inspection.previous_inspection = prev

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
