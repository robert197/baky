"""Tests for Photo model storage integration — thumbnail generation, HEIC conversion, validation."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.inspections.models import Photo
from tests.factories import InspectionFactory, PhotoFactory


def _make_image(width=800, height=600, fmt="JPEG", name="test.jpg"):
    img = Image.new("RGB", (width, height), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=f"image/{fmt.lower()}")


@pytest.mark.django_db
class TestPhotoThumbnailGeneration:
    def test_thumbnail_auto_generated_on_create(self):
        photo = PhotoFactory()
        assert photo.thumbnail
        assert photo.thumbnail.name

    def test_thumbnail_dimensions_within_limit(self):
        large_file = _make_image(1920, 1080, name="large.jpg")
        inspection = InspectionFactory()
        photo = Photo(inspection=inspection, file=large_file, caption="Groß")
        photo.save()
        img = Image.open(photo.thumbnail)
        assert img.width <= 300
        assert img.height <= 300

    def test_thumbnail_preserves_aspect_ratio(self):
        wide_file = _make_image(1000, 500, name="wide.jpg")
        inspection = InspectionFactory()
        photo = Photo(inspection=inspection, file=wide_file, caption="Breit")
        photo.save()
        img = Image.open(photo.thumbnail)
        ratio = img.width / img.height
        assert abs(ratio - 2.0) < 0.1

    def test_small_image_thumbnail_not_upscaled(self):
        small_file = _make_image(100, 80, name="small.jpg")
        inspection = InspectionFactory()
        photo = Photo(inspection=inspection, file=small_file, caption="Klein")
        photo.save()
        img = Image.open(photo.thumbnail)
        assert img.width == 100
        assert img.height == 80

    def test_png_gets_jpeg_thumbnail(self):
        png_file = _make_image(400, 300, fmt="PNG", name="test.png")
        inspection = InspectionFactory()
        photo = Photo(inspection=inspection, file=png_file, caption="PNG")
        photo.save()
        img = Image.open(photo.thumbnail)
        assert img.format == "JPEG"

    def test_existing_thumbnail_not_overwritten_on_update(self):
        photo = PhotoFactory()
        original_thumb = photo.thumbnail.name
        photo.caption = "Aktualisiert"
        photo.save()
        assert photo.thumbnail.name == original_thumb


@pytest.mark.django_db
class TestPhotoUploadPath:
    def test_upload_path_contains_photos_prefix(self):
        photo = PhotoFactory()
        assert "photos/" in photo.file.name

    def test_thumbnail_path_contains_thumbs_prefix(self):
        photo = PhotoFactory()
        assert "photos/thumbs/" in photo.thumbnail.name


@pytest.mark.django_db
class TestPhotoValidation:
    def test_validator_attached_to_file_field(self):
        validators = Photo._meta.get_field("file").validators
        from baky.storage import validate_photo_file

        assert validate_photo_file in validators

    def test_valid_jpeg_accepted(self):
        file = _make_image(name="valid.jpg")
        inspection = InspectionFactory()
        photo = Photo(inspection=inspection, file=file, caption="OK")
        photo.full_clean()  # Should not raise

    def test_valid_png_accepted(self):
        file = _make_image(fmt="PNG", name="valid.png")
        inspection = InspectionFactory()
        photo = Photo(inspection=inspection, file=file, caption="OK")
        photo.full_clean()  # Should not raise


@pytest.mark.django_db
class TestPhotoSignedUrl:
    def test_get_signed_url_returns_url(self):
        from baky.storage import get_signed_url

        photo = PhotoFactory()
        url = get_signed_url(photo.file)
        assert url is not None
        assert "photos/" in url

    def test_get_signed_url_for_thumbnail(self):
        from baky.storage import get_signed_url

        photo = PhotoFactory()
        url = get_signed_url(photo.thumbnail)
        assert url is not None

    def test_get_signed_url_returns_none_for_empty(self):
        from baky.storage import get_signed_url

        assert get_signed_url(None) is None
