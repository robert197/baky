from django.urls import path

from . import views

app_name = "inspections"

urlpatterns = [
    path("", views.index, name="index"),
    path("schedule/", views.schedule, name="schedule"),
    path("schedule/<int:inspection_id>/access/", views.access_details, name="access_details"),
]
