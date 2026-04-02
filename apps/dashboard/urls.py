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
]
