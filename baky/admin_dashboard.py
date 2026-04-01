from datetime import timedelta

from django.utils import timezone


def dashboard_callback(request, context):
    """Provide key metrics for the BAKY admin dashboard."""
    from apps.apartments.models import Apartment
    from apps.inspections.models import Inspection, InspectionItem

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    week_start = now - timedelta(days=now.weekday())  # Monday of this week

    context.update(
        {
            "active_apartments": Apartment.objects.filter(status="active").count(),
            "inspections_this_week": Inspection.objects.filter(
                scheduled_at__gte=week_start,
                scheduled_at__lt=week_start + timedelta(days=7),
            ).count(),
            "pending_inspections": Inspection.objects.filter(status="scheduled").count(),
            "urgent_findings": InspectionItem.objects.filter(
                severity="urgent",
                inspection__completed_at__gte=week_ago,
            ).count(),
        }
    )
    return context
