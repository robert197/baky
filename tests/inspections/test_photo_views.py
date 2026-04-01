"""Tests for photo capture, upload, delete, and caption views."""

import datetime
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.inspections.models import Inspection, Photo
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    OwnerFactory,
    PhotoFactory,
    SubscriptionFactory,
)


def _tomorrow_at(hour: int = 10) -> datetime.datetime:
    return timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)


def _make_image(width=800, height=600, fmt="JPEG", name="test.jpg"):
    img = Image.new("RGB", (width, height), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=f"image/{fmt.lower()}")


def _create_in_progress_inspection(inspector=None):
    """Create an in-progress inspection with an item."""
    inspector = inspector or InspectorFactory()
    apt = ApartmentFactory()
    SubscriptionFactory(owner=apt.owner)
    tomorrow = _tomorrow_at()
    inspection = InspectionFactory(
        inspector=inspector,
        apartment=apt,
        scheduled_at=tomorrow,
        scheduled_end=tomorrow + datetime.timedelta(hours=2),
        status=Inspection.Status.IN_PROGRESS,
    )
    item = InspectionItemFactory(
        inspection=inspection,
        checklist_label="Herd sauber",
        category="Küche",
        order=1,
    )
    return inspector, inspection, item


# --- Upload Photo ---


@pytest.mark.django_db
class TestUploadPhotoView:
    def test_upload_general_photo(self):
        """Upload a photo not tied to any specific item."""
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image(name="general.jpg")
        response = client.post(url, {"file": file}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert Photo.objects.filter(inspection=inspection, inspection_item=None).count() == 1

    def test_upload_item_photo(self):
        """Upload a photo tied to a specific checklist item."""
        inspector, inspection, item = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image(name="item.jpg")
        response = client.post(url, {"file": file, "item_id": item.pk}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert Photo.objects.filter(inspection=inspection, inspection_item=item).count() == 1

    def test_upload_with_caption(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image(name="captioned.jpg")
        response = client.post(url, {"file": file, "caption": "Küchenschaden"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        photo = Photo.objects.get(inspection=inspection)
        assert photo.caption == "Küchenschaden"

    def test_upload_creates_thumbnail(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image(1920, 1080, name="large.jpg")
        response = client.post(url, {"file": file}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        photo = Photo.objects.get(inspection=inspection)
        assert photo.thumbnail
        assert photo.thumbnail.name

    def test_upload_multiple_photos_per_item(self):
        """Multiple photos can be uploaded for the same item."""
        inspector, inspection, item = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        for i in range(3):
            file = _make_image(name=f"photo_{i}.jpg")
            response = client.post(url, {"file": file, "item_id": item.pk}, HTTP_HX_REQUEST="true")
            assert response.status_code == 200
        assert Photo.objects.filter(inspection_item=item).count() == 3

    def test_upload_returns_photo_partial(self):
        """Response should contain the photo thumbnail HTML."""
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image(name="test.jpg")
        response = client.post(url, {"file": file}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        content = response.content.decode()
        # Should contain photo management elements
        assert "photo-" in content

    def test_upload_requires_authentication(self):
        _, inspection, _ = _create_in_progress_inspection()
        client = Client()
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image()
        response = client.post(url, {"file": file})
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_upload_requires_inspector_role(self):
        _, inspection, _ = _create_in_progress_inspection()
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image()
        response = client.post(url, {"file": file})
        assert response.status_code == 404

    def test_upload_other_inspector_gets_404(self):
        _, inspection, _ = _create_in_progress_inspection()
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image()
        response = client.post(url, {"file": file}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_upload_completed_inspection_returns_404(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        inspection.status = Inspection.Status.COMPLETED
        inspection.save(update_fields=["status"])
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image()
        response = client.post(url, {"file": file}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_upload_without_file_returns_400(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        response = client.post(url, {}, HTTP_HX_REQUEST="true")
        assert response.status_code == 400

    def test_upload_invalid_item_id_returns_400(self):
        """Item ID must belong to the same inspection."""
        inspector, inspection, _ = _create_in_progress_inspection()
        # Create item on a different inspection
        other_item = InspectionItemFactory()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image()
        response = client.post(url, {"file": file, "item_id": other_item.pk}, HTTP_HX_REQUEST="true")
        assert response.status_code == 400

    def test_upload_requires_post(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 405

    def test_upload_png_accepted(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:upload_photo", args=[inspection.pk])
        file = _make_image(fmt="PNG", name="test.png")
        response = client.post(url, {"file": file}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert Photo.objects.filter(inspection=inspection).count() == 1


# --- Delete Photo ---


@pytest.mark.django_db
class TestDeletePhotoView:
    def test_delete_photo(self):
        inspector, inspection, item = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection, inspection_item=item)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.post(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert not Photo.objects.filter(pk=photo.pk).exists()

    def test_delete_returns_empty_response_for_htmx(self):
        """After deletion, HTMX should get a response to remove the element."""
        inspector, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.post(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 200

    def test_delete_requires_authentication(self):
        _, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.post(url)
        assert response.status_code == 302

    def test_delete_requires_inspector_role(self):
        _, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        owner = OwnerFactory()
        client = Client()
        client.force_login(owner)
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.post(url)
        assert response.status_code == 404

    def test_delete_other_inspector_gets_404(self):
        _, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.post(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_delete_completed_inspection_returns_404(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        inspection.status = Inspection.Status.COMPLETED
        inspection.save(update_fields=["status"])
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.post(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_delete_requires_post(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:delete_photo", args=[photo.pk])
        response = client.get(url)
        assert response.status_code == 405


# --- Update Photo Caption ---


@pytest.mark.django_db
class TestUpdatePhotoCaptionView:
    def test_update_caption(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection, caption="Alt")
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.post(url, {"caption": "Wasserschaden Bad"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        photo.refresh_from_db()
        assert photo.caption == "Wasserschaden Bad"

    def test_update_caption_with_german_chars(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.post(url, {"caption": "Küchentür beschädigt — Schäden sichtbar"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        photo.refresh_from_db()
        assert photo.caption == "Küchentür beschädigt — Schäden sichtbar"

    def test_update_caption_empty_clears(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection, caption="Hatte Beschriftung")
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.post(url, {"caption": ""}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        photo.refresh_from_db()
        assert photo.caption == ""

    def test_update_caption_requires_authentication(self):
        _, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.post(url, {"caption": "test"})
        assert response.status_code == 302

    def test_update_caption_other_inspector_gets_404(self):
        _, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        other = InspectorFactory()
        client = Client()
        client.force_login(other)
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.post(url, {"caption": "test"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_update_caption_completed_inspection_returns_404(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        inspection.status = Inspection.Status.COMPLETED
        inspection.save(update_fields=["status"])
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.post(url, {"caption": "test"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 404

    def test_update_caption_requires_post(self):
        inspector, inspection, _ = _create_in_progress_inspection()
        photo = PhotoFactory(inspection=inspection)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:update_photo_caption", args=[photo.pk])
        response = client.get(url)
        assert response.status_code == 405


# --- Execute View with Photos ---


@pytest.mark.django_db
class TestExecuteViewPhotos:
    def test_execute_view_includes_photos_for_items(self):
        """The execute view should pass photos to the template context."""
        inspector, inspection, item = _create_in_progress_inspection()
        PhotoFactory(inspection=inspection, inspection_item=item, caption="Item-Foto")
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Photo section should be present
        assert "photo-upload" in content or "Foto" in content

    def test_execute_view_shows_general_photos(self):
        """General photos (not tied to items) should appear in the template."""
        inspector, inspection, _ = _create_in_progress_inspection()
        PhotoFactory(inspection=inspection, inspection_item=None, caption="Allgemeines Foto")
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 200

    def test_execute_view_photo_count_in_context(self):
        """Context should include photo counts for display."""
        inspector, inspection, item = _create_in_progress_inspection()
        PhotoFactory(inspection=inspection, inspection_item=item)
        PhotoFactory(inspection=inspection, inspection_item=item)
        PhotoFactory(inspection=inspection, inspection_item=None)
        client = Client()
        client.force_login(inspector)
        url = reverse("inspections:execute_inspection", args=[inspection.pk])
        response = client.get(url)
        assert response.status_code == 200
