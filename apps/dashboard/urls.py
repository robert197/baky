from django.urls import path

from apps.reports import views as report_views

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("apartments/<int:pk>/", views.apartment_detail, name="apartment_detail"),
    path("apartments/<int:pk>/edit/", views.apartment_edit, name="apartment_edit"),
    path("apartments/<int:pk>/inspections/", views.inspection_timeline, name="inspection_timeline"),
    path(
        "apartments/<int:pk>/inspections/<int:inspection_pk>/summary/",
        views.inspection_summary,
        name="inspection_summary",
    ),
    path(
        "apartments/<int:pk>/inspections/<int:inspection_pk>/report/",
        views.inspection_report_detail,
        name="inspection_report_detail",
    ),
    path("reports/<int:report_id>/", report_views.report_detail, name="report_detail"),
    # Booking
    path("buchen/", views.booking_calendar, name="booking_calendar"),
    path("buchen/slot/", views.book_slot, name="book_slot"),
    path("buchen/stornieren/<int:pk>/", views.cancel_booking, name="cancel_booking"),
    # Subscription management
    path("subscription/", views.subscription_overview, name="subscription"),
    path("subscription/change/", views.subscription_change, name="subscription_change"),
    path("subscription/pause/", views.subscription_pause, name="subscription_pause"),
    path("subscription/cancel/", views.subscription_cancel, name="subscription_cancel"),
    path("subscription/extra/", views.subscription_extra, name="subscription_extra"),
    path("subscription/billing/", views.subscription_billing, name="subscription_billing"),
    # Account / GDPR
    path("account/delete/", views.account_delete, name="account_delete"),
    path("account/export/", views.data_export_request, name="data_export"),
]
