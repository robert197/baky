from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import owner_required
from apps.inspections.models import Photo


@owner_required
def report_detail(request, report_id):
    """Display a report to the apartment owner."""
    from apps.reports.models import Report

    report = get_object_or_404(
        Report.objects.select_related("inspection__apartment__owner", "inspection__inspector"),
        pk=report_id,
    )
    if report.inspection.apartment.owner_id != request.user.id:
        raise Http404

    return render(request, "reports/report_detail.html", {"report": report})


@owner_required
def report_photo(request, photo_id):
    """Proxy endpoint: redirect to a fresh signed URL for a report photo."""
    photo = get_object_or_404(
        Photo.objects.select_related("inspection__apartment__owner"),
        pk=photo_id,
    )
    if photo.inspection.apartment.owner_id != request.user.id:
        raise Http404

    url = photo.get_file_url()
    if not url:
        raise Http404

    return redirect(url)
