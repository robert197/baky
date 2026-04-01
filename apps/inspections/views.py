from django.shortcuts import render
from django.utils import timezone

from apps.accounts.decorators import inspector_required

from .models import Inspection


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
