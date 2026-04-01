from django.urls import path

from apps.reports import views as report_views

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("reports/<int:report_id>/", report_views.report_detail, name="report_detail"),
]
