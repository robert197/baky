import zoneinfo
from datetime import date as date_type
from datetime import datetime, timedelta
from itertools import groupby

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, Max, Min, OuterRef, Q, Subquery
from django.db.models.functions import Now
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import owner_required
from apps.accounts.models import Subscription
from apps.apartments.models import Apartment
from apps.dashboard.forms import (
    ApartmentEditForm,
    BookingApartmentForm,
    ExtraInspectionForm,
    PlanChangeRequestForm,
    SubscriptionActionForm,
)
from apps.inspections.models import Inspection, InspectionItem
from apps.reports.models import Report

VIENNA_TZ = zoneinfo.ZoneInfo("Europe/Vienna")


def _get_subscription_or_none(user):
    """Safely get a user's subscription, handling OneToOneField DoesNotExist."""
    try:
        return user.subscription
    except Subscription.DoesNotExist:
        return None


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
    subscription = _get_subscription_or_none(request.user)
    return render(
        request,
        "dashboard/index.html",
        {"apartments": apartments, "subscription": subscription, "active": "apartments"},
    )


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


def _parse_date(value: str | None) -> date_type | None:
    if not value:
        return None
    try:
        return date_type.fromisoformat(value)
    except ValueError:
        return None


def _base_inspection_qs(apartment):
    """Shared queryset for completed inspections with annotations."""
    return (
        apartment.inspections.filter(status=Inspection.Status.COMPLETED)
        .annotate(
            has_report=Exists(
                Report.objects.filter(
                    inspection=OuterRef("pk"),
                    status=Report.Status.COMPLETED,
                ).exclude(html_content="")
            ),
            flagged_count=Count("items", filter=Q(items__result=InspectionItem.Result.FLAGGED)),
            photo_count=Count("photos", distinct=True),
        )
        .select_related("inspector", "report")
    )


@owner_required
def inspection_timeline(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    inspections = _base_inspection_qs(apartment).order_by("-completed_at")

    # Filters
    rating = request.GET.get("rating")
    if rating in ("ok", "attention", "urgent"):
        inspections = inspections.filter(overall_rating=rating)
    date_from = _parse_date(request.GET.get("from"))
    if date_from:
        inspections = inspections.filter(completed_at__date__gte=date_from)
    date_to = _parse_date(request.GET.get("to"))
    if date_to:
        inspections = inspections.filter(completed_at__date__lte=date_to)

    # Pagination
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 10
    total = inspections.count()
    inspections_page = inspections[(page - 1) * per_page : page * per_page]
    has_more = page * per_page < total

    context = {
        "apartment": apartment,
        "inspections": inspections_page,
        "has_more": has_more,
        "next_page": page + 1,
        "active": "apartments",
        "current_rating": rating or "",
        "current_from": date_from.isoformat() if date_from else "",
        "current_to": date_to.isoformat() if date_to else "",
    }

    if request.headers.get("HX-Request") and request.GET.get("page"):
        return render(request, "dashboard/_inspection_timeline_items.html", context)

    return render(request, "dashboard/inspection_timeline.html", context)


@owner_required
def inspection_summary(request, pk, inspection_pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    inspection = get_object_or_404(
        _base_inspection_qs(apartment),
        pk=inspection_pk,
    )
    return render(
        request,
        "dashboard/_inspection_summary.html",
        {"apartment": apartment, "inspection": inspection},
    )


@owner_required
def inspection_report_detail(request, pk, inspection_pk):
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    inspection = get_object_or_404(
        apartment.inspections.filter(status=Inspection.Status.COMPLETED).select_related("inspector"),
        pk=inspection_pk,
    )
    items = inspection.items.all().prefetch_related("photos").order_by("category", "order")

    grouped_items = []
    for category, group in groupby(items, key=lambda i: i.category):
        group_list = list(group)
        flagged_in_group = sum(1 for i in group_list if i.result == InspectionItem.Result.FLAGGED)
        grouped_items.append(
            {
                "category": category,
                "items": group_list,
                "flagged_count": flagged_in_group,
            }
        )

    general_photos = inspection.photos.filter(inspection_item__isnull=True)

    try:
        report = inspection.report if inspection.report.is_ready else None
    except Report.DoesNotExist:
        report = None

    duration_display = ""
    if inspection.started_at and inspection.completed_at:
        delta = inspection.completed_at - inspection.started_at
        total_minutes = int(delta.total_seconds()) // 60
        hours, minutes = divmod(total_minutes, 60)
        if hours:
            duration_display = f"{hours} Std. {minutes} Min."
        else:
            duration_display = f"{minutes} Min."

    return render(
        request,
        "dashboard/inspection_report_detail.html",
        {
            "apartment": apartment,
            "inspection": inspection,
            "grouped_items": grouped_items,
            "general_photos": general_photos,
            "report": report,
            "duration_display": duration_display,
            "active": "apartments",
        },
    )


# --- Subscription views ---


@owner_required
def subscription_overview(request):
    subscription = _get_subscription_or_none(request.user)
    return render(
        request,
        "dashboard/subscription.html",
        {"subscription": subscription, "active": "subscription"},
    )


@owner_required
def subscription_change(request):
    subscription = _get_subscription_or_none(request.user)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        messages.warning(request, "Planänderung ist nur mit einem aktiven Abonnement möglich.")
        return redirect("dashboard:subscription")

    if request.method == "POST":
        form = PlanChangeRequestForm(request.POST)
        if form.is_valid():
            from baky.tasks import queue_task

            queue_task(
                "apps.dashboard.tasks.send_plan_change_notification",
                request.user.pk,
                form.cleaned_data["requested_plan"],
                form.cleaned_data.get("message", ""),
                task_name=f"plan_change_{request.user.pk}",
            )
            messages.success(request, "Ihre Anfrage zur Planänderung wurde gesendet.")
            return redirect("dashboard:subscription")
    else:
        form = PlanChangeRequestForm(initial={"requested_plan": subscription.plan})

    return render(
        request,
        "dashboard/subscription_change.html",
        {"form": form, "subscription": subscription, "active": "subscription"},
    )


@owner_required
def subscription_pause(request):
    subscription = _get_subscription_or_none(request.user)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        messages.warning(request, "Pausierung ist nur mit einem aktiven Abonnement möglich.")
        return redirect("dashboard:subscription")

    if request.method == "POST":
        form = SubscriptionActionForm(request.POST)
        if form.is_valid():
            from baky.tasks import queue_task

            queue_task(
                "apps.dashboard.tasks.send_subscription_action_notification",
                request.user.pk,
                "pause",
                form.cleaned_data.get("reason", ""),
                task_name=f"pause_request_{request.user.pk}",
            )
            messages.success(request, "Ihre Anfrage zur Pausierung wurde gesendet.")
            return redirect("dashboard:subscription")
    else:
        form = SubscriptionActionForm()

    return render(
        request,
        "dashboard/subscription_pause.html",
        {"form": form, "subscription": subscription, "active": "subscription"},
    )


@owner_required
def subscription_cancel(request):
    subscription = _get_subscription_or_none(request.user)
    if not subscription or subscription.status == Subscription.Status.CANCELLED:
        messages.warning(request, "Kündigung ist nicht möglich.")
        return redirect("dashboard:subscription")

    if request.method == "POST":
        form = SubscriptionActionForm(request.POST)
        if form.is_valid():
            from baky.tasks import queue_task

            queue_task(
                "apps.dashboard.tasks.send_subscription_action_notification",
                request.user.pk,
                "cancel",
                form.cleaned_data.get("reason", ""),
                task_name=f"cancel_request_{request.user.pk}",
            )
            messages.success(request, "Ihre Anfrage zur Kündigung wurde gesendet.")
            return redirect("dashboard:subscription")
    else:
        form = SubscriptionActionForm()

    return render(
        request,
        "dashboard/subscription_cancel.html",
        {"form": form, "subscription": subscription, "active": "subscription"},
    )


@owner_required
def subscription_extra(request):
    subscription = _get_subscription_or_none(request.user)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        messages.warning(request, "Zusätzliche Inspektionen sind nur mit einem aktiven Abonnement möglich.")
        return redirect("dashboard:subscription")

    if request.method == "POST":
        form = ExtraInspectionForm(request.POST, owner=request.user)
        if form.is_valid():
            from baky.tasks import queue_task

            queue_task(
                "apps.dashboard.tasks.send_extra_inspection_notification",
                request.user.pk,
                form.cleaned_data["apartment"].pk,
                str(form.cleaned_data["preferred_date"]),
                form.cleaned_data.get("notes", ""),
                task_name=f"extra_inspection_{request.user.pk}",
            )
            messages.success(request, "Ihre Anfrage für eine zusätzliche Inspektion wurde gesendet.")
            return redirect("dashboard:subscription")
    else:
        form = ExtraInspectionForm(owner=request.user)

    return render(
        request,
        "dashboard/subscription_extra.html",
        {"form": form, "subscription": subscription, "active": "subscription"},
    )


@owner_required
def subscription_billing(request):
    subscription = _get_subscription_or_none(request.user)
    return render(
        request,
        "dashboard/subscription_billing.html",
        {"subscription": subscription, "active": "subscription"},
    )


# --- Booking views ---


def _get_week_availability(start_date, apartment, owner):
    """Return availability data for a 7-day week starting at start_date."""
    subscription = _get_subscription_or_none(owner)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        return {"days": [], "used": 0, "limit": 0, "limit_reached": True}

    used = subscription.get_inspections_used_this_month()
    limit = subscription.get_monthly_inspection_limit()
    limit_reached = used >= limit

    now = timezone.now()
    week_dates = [start_date + timedelta(days=i) for i in range(7)]

    # Batch query: find all dates in this week that already have bookings for this apartment
    booked_dates = set(
        Inspection.objects.filter(
            apartment=apartment,
            scheduled_at__date__in=week_dates,
            status__in=[Inspection.Status.SCHEDULED, Inspection.Status.IN_PROGRESS, Inspection.Status.COMPLETED],
        )
        .values_list("scheduled_at__date", flat=True)
        .distinct()
    )

    days = []
    for current_date in week_dates:
        day_slots = []
        has_day_booking = current_date in booked_dates

        for slot_key in Inspection.TimeSlot:
            sh, sm, eh, em = Inspection.SLOT_TIMES[slot_key]
            slot_start = datetime(current_date.year, current_date.month, current_date.day, sh, sm, tzinfo=VIENNA_TZ)

            is_past = now >= slot_start - timedelta(hours=24)

            day_slots.append(
                {
                    "key": slot_key.value,
                    "label": slot_key.label,
                    "start": f"{sh:02d}:{sm:02d}",
                    "end": f"{eh:02d}:{em:02d}",
                    "available": not is_past and not has_day_booking and not limit_reached,
                    "is_past": is_past,
                    "has_booking": has_day_booking,
                }
            )
        days.append({"date": current_date, "slots": day_slots})

    return {"days": days, "used": used, "limit": limit, "limit_reached": limit_reached}


@owner_required
def booking_calendar(request):
    subscription = _get_subscription_or_none(request.user)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        messages.warning(request, "Terminbuchung ist nur mit einem aktiven Abonnement möglich.")
        return redirect("dashboard:subscription")

    apartments = Apartment.objects.filter(owner=request.user, status=Apartment.Status.ACTIVE)
    if not apartments.exists():
        messages.info(request, "Bitte fügen Sie zuerst eine Wohnung hinzu.")
        return redirect("dashboard:index")

    # Parse week offset for navigation
    try:
        week_offset = int(request.GET.get("week", 0))
    except (ValueError, TypeError):
        week_offset = 0
    week_offset = max(0, min(52, week_offset))

    today = date_type.today()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)

    # Selected apartment
    selected_apartment = None
    apartment_id = request.GET.get("apartment")
    if apartment_id:
        selected_apartment = get_object_or_404(
            Apartment, pk=apartment_id, owner=request.user, status=Apartment.Status.ACTIVE
        )
    elif apartments.count() == 1:
        selected_apartment = apartments.first()

    availability = None
    if selected_apartment:
        availability = _get_week_availability(start_of_week, selected_apartment, request.user)

    form = BookingApartmentForm(owner=request.user)
    if selected_apartment:
        form = BookingApartmentForm(initial={"apartment": selected_apartment.pk}, owner=request.user)

    end_of_week = start_of_week + timedelta(days=6)

    context = {
        "form": form,
        "apartments": apartments,
        "selected_apartment": selected_apartment,
        "availability": availability,
        "week_offset": week_offset,
        "start_of_week": start_of_week,
        "end_of_week": end_of_week,
        "subscription": subscription,
        "active": "booking",
    }

    if request.headers.get("HX-Request"):
        return render(request, "dashboard/_calendar_week.html", context)
    return render(request, "dashboard/booking_calendar.html", context)


@owner_required
def book_slot(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    subscription = _get_subscription_or_none(request.user)
    if not subscription or subscription.status != Subscription.Status.ACTIVE:
        return render(
            request,
            "dashboard/_booking_error.html",
            {"error": "Terminbuchung ist nur mit einem aktiven Abonnement möglich."},
        )

    apartment_id = request.POST.get("apartment")
    slot_date = request.POST.get("date")
    slot_key = request.POST.get("slot")

    apartment = get_object_or_404(Apartment, pk=apartment_id, owner=request.user, status=Apartment.Status.ACTIVE)

    # Validate slot key
    try:
        time_slot = Inspection.TimeSlot(slot_key)
    except ValueError:
        return render(request, "dashboard/_booking_error.html", {"error": "Ungültiger Zeitslot."})

    try:
        target_date = date_type.fromisoformat(slot_date)
    except (ValueError, TypeError):
        return render(request, "dashboard/_booking_error.html", {"error": "Ungültiges Datum."})

    sh, sm, eh, em = Inspection.SLOT_TIMES[time_slot]
    scheduled_at = datetime(target_date.year, target_date.month, target_date.day, sh, sm, tzinfo=VIENNA_TZ)
    scheduled_end = datetime(target_date.year, target_date.month, target_date.day, eh, em, tzinfo=VIENNA_TZ)

    # 24-hour advance check
    if timezone.now() >= scheduled_at - timedelta(hours=24):
        return render(
            request,
            "dashboard/_booking_error.html",
            {"error": "Buchungen müssen mindestens 24 Stunden im Voraus erfolgen."},
        )

    inspection = Inspection(
        apartment=apartment,
        inspector=None,
        scheduled_at=scheduled_at,
        scheduled_end=scheduled_end,
        time_slot=slot_key,
        status=Inspection.Status.SCHEDULED,
    )

    try:
        inspection.full_clean()
        inspection.save()
    except ValidationError as e:
        error_msg = ". ".join(msg for msgs in e.message_dict.values() for msg in msgs)
        return render(request, "dashboard/_booking_error.html", {"error": error_msg})

    # Notify admin
    from baky.tasks import queue_task

    queue_task(
        "apps.dashboard.tasks.send_booking_notification",
        request.user.pk,
        inspection.pk,
        task_name=f"booking_notification_{inspection.pk}",
    )

    return render(
        request,
        "dashboard/_booking_success.html",
        {"inspection": inspection, "apartment": apartment},
    )
