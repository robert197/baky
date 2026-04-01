from django.urls import path

from . import views

app_name = "inspections"

urlpatterns = [
    path("", views.index, name="index"),
    path("schedule/", views.schedule, name="schedule"),
    path("schedule/<int:inspection_id>/access/", views.access_details, name="access_details"),
    path("<int:inspection_id>/start/", views.start_inspection, name="start_inspection"),
    path("<int:inspection_id>/execute/", views.execute_inspection, name="execute_inspection"),
    path("items/<int:item_id>/update/", views.update_item, name="update_item"),
    path("<int:inspection_id>/notes/", views.update_general_notes, name="update_general_notes"),
    # Photo endpoints
    path("<int:inspection_id>/photos/upload/", views.upload_photo, name="upload_photo"),
    path("photos/<int:photo_id>/delete/", views.delete_photo, name="delete_photo"),
    path("photos/<int:photo_id>/caption/", views.update_photo_caption, name="update_photo_caption"),
]
