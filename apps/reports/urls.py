from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("photos/<int:photo_id>/", views.report_photo, name="report_photo"),
]
