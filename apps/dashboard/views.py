from django.contrib import messages
from django.db.models import Exists, Max, Min, OuterRef, Q, Subquery
from django.db.models.functions import Now
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import owner_required
from apps.apartments.models import Apartment
from apps.dashboard.forms import ApartmentEditForm
from apps.inspections.models import Inspection
from apps.reports.models import Report


@owner_required
def index(request):
    apartments = (
        Apartment.objects.filter(owner=request.user)
        .exclude(status=Apartment.Status.ARCHIVED)
        .annotate(
            last_inspection_date=Max(
                "inspections__completed_at",
                filter=Q(inspections__status=Inspection.Status.COMPLETED),
            ),
            last_inspection_rating=Subquery(
                Inspection.objects.filter(
                    apartment=OuterRef("pk"),
                    status=Inspection.Status.COMPLETED,
                )
                .order_by("-completed_at")
                .values("overall_rating")[:1]
            ),
            next_inspection_date=Min(
                "inspections__scheduled_at",
                filter=Q(
                    inspections__status=Inspection.Status.SCHEDULED,
                    inspections__scheduled_at__gt=Now(),
                ),
            ),
        )
    )
    return render(request, "dashboard/index.html", {"apartments": apartments, "active": "apartments"})


@owner_required
def apartment_detail(request, pk):
    apartment = get_object_or_404(Apartment.objects.select_related("checklist_template"), pk=pk, owner=request.user)
    checklist = getattr(apartment, "checklist_template", None)
    recent_inspections = (
        apartment.inspections.filter(status=Inspection.Status.COMPLETED)
        .annotate(
            has_report=Exists(
                Report.objects.filter(
                    inspection=OuterRef("pk"),
                    status=Report.Status.COMPLETED,
                ).exclude(html_content="")
            ),
        )
        .select_related("report")
        .order_by("-completed_at")[:5]
    )
    return render(
        request,
        "dashboard/apartment_detail.html",
        {
            "apartment": apartment,
            "checklist": checklist,
            "recent_inspections": recent_inspections,
            "active": "apartments",
        },
    )


@owner_required
def apartment_edit(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    if request.method == "POST":
        form = ApartmentEditForm(request.POST, instance=apartment)
        if form.is_valid():
            form.save()
            messages.success(request, f"Wohnung '{apartment.address}' gespeichert.")
            return redirect("dashboard:index")
    else:
        form = ApartmentEditForm(instance=apartment)
    return render(
        request, "dashboard/apartment_edit.html", {"apartment": apartment, "form": form, "active": "apartments"}
    )
