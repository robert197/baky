"""Tests for baky.storage — photo validation, thumbnail generation, and signed URLs."""

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from baky.storage import (
    ACCEPTED_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    THUMBNAIL_MAX_SIZE,
    create_thumbnail,
    generate_thumbnail_path,
    generate_upload_path,
    get_signed_url,
    validate_photo_file,
)


def _make_image(width=800, height=600, fmt="JPEG", name="test.jpg"):
    """Helper: create an in-memory image file."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=f"image/{fmt.lower()}")


def _make_png(width=800, height=600, name="test.png"):
    return _make_image(width, height, fmt="PNG", name=name)


class TestValidatePhotoFile:
    def test_valid_jpeg(self):
        file = _make_image(name="photo.jpg")
        validate_photo_file(file)  # Should not raise

    def test_valid_png(self):
        file = _make_png(name="photo.png")
        validate_photo_file(file)  # Should not raise

    def test_valid_heic_extension(self):
        """HEIC extension is accepted (actual content validation is not done here)."""
        file = SimpleUploadedFile("photo.heic", b"fake-heic-data", content_type="image/heic")
        file.size = 1024  # 1 KB
        validate_photo_file(file)  # Should not raise

    def test_rejects_too_large(self):
        file = _make_image(name="big.jpg")
        file.size = MAX_UPLOAD_SIZE + 1
        with pytest.raises(ValidationError, match="10 MB"):
            validate_photo_file(file)

    def test_rejects_unsupported_extension(self):
        file = SimpleUploadedFile("doc.pdf", b"fake", content_type="application/pdf")
        file.size = 1024
        with pytest.raises(ValidationError, match="Nicht unterstütztes Dateiformat"):
            validate_photo_file(file)

    def test_rejects_gif(self):
        file = SimpleUploadedFile("animation.gif", b"fake", content_type="image/gif")
        file.size = 1024
        with pytest.raises(ValidationError, match="Nicht unterstütztes Dateiformat"):
            validate_photo_file(file)

    def test_exact_max_size_accepted(self):
        file = _make_image(name="exact.jpg")
        file.size = MAX_UPLOAD_SIZE
        validate_photo_file(file)  # Should not raise

    def test_accepted_extensions_complete(self):
        assert ACCEPTED_EXTENSIONS == {".jpg", ".jpeg", ".png", ".heic", ".heif"}


class TestGenerateUploadPath:
    def test_returns_photos_prefix(self):
        path = generate_upload_path(None, "my_photo.jpg")
        assert path.startswith("photos/")

    def test_preserves_jpg_extension(self):
        path = generate_upload_path(None, "my_photo.jpg")
        assert path.endswith(".jpg")

    def test_preserves_png_extension(self):
        path = generate_upload_path(None, "my_photo.png")
        assert path.endswith(".png")

    def test_converts_heic_to_jpg_extension(self):
        path = generate_upload_path(None, "my_photo.heic")
        assert path.endswith(".jpg")

    def test_converts_heif_to_jpg_extension(self):
        path = generate_upload_path(None, "my_photo.HEIF")
        assert path.endswith(".jpg")

    def test_unique_filenames(self):
        path1 = generate_upload_path(None, "same.jpg")
        path2 = generate_upload_path(None, "same.jpg")
        assert path1 != path2

    def test_contains_year_month(self):
        from django.utils import timezone

        now = timezone.now()
        path = generate_upload_path(None, "test.jpg")
        assert f"/{now.year}/" in path
        assert f"/{now.month:02d}/" in path


class TestGenerateThumbnailPath:
    def test_returns_thumbs_prefix(self):
        path = generate_thumbnail_path(None, "thumb.jpg")
        assert "photos/thumbs/" in path

    def test_always_jpg_extension(self):
        path = generate_thumbnail_path(None, "original.png")
        assert path.endswith(".jpg")

    def test_unique_filenames(self):
        path1 = generate_thumbnail_path(None, "same.jpg")
        path2 = generate_thumbnail_path(None, "same.jpg")
        assert path1 != path2


class TestCreateThumbnail:
    def test_creates_thumbnail(self):
        source = _make_image(800, 600, name="source.jpg")
        thumb = create_thumbnail(source)
        assert isinstance(thumb, ContentFile)
        assert len(thumb.read()) > 0

    def test_thumbnail_within_max_size(self):
        source = _make_image(1920, 1080, name="large.jpg")
        thumb = create_thumbnail(source)
        img = Image.open(io.BytesIO(thumb.read()))
        assert img.width <= THUMBNAIL_MAX_SIZE[0]
        assert img.height <= THUMBNAIL_MAX_SIZE[1]

    def test_maintains_aspect_ratio(self):
        source = _make_image(1000, 500, name="wide.jpg")
        thumb = create_thumbnail(source)
        img = Image.open(io.BytesIO(thumb.read()))
        # Original is 2:1, thumbnail should maintain ratio
        ratio = img.width / img.height
        assert abs(ratio - 2.0) < 0.1

    def test_small_image_not_upscaled(self):
        source = _make_image(100, 100, name="small.jpg")
        thumb = create_thumbnail(source)
        img = Image.open(io.BytesIO(thumb.read()))
        assert img.width == 100
        assert img.height == 100

    def test_thumbnail_is_jpeg(self):
        source = _make_png(400, 300, name="source.png")
        thumb = create_thumbnail(source)
        img = Image.open(io.BytesIO(thumb.read()))
        assert img.format == "JPEG"

    def test_square_image_thumbnail(self):
        source = _make_image(1000, 1000, name="square.jpg")
        thumb = create_thumbnail(source)
        img = Image.open(io.BytesIO(thumb.read()))
        assert img.width == 300
        assert img.height == 300


class TestGetSignedUrl:
    def test_returns_none_for_empty_field(self):
        result = get_signed_url(None)
        assert result is None

    def test_returns_none_for_falsy_field(self):
        result = get_signed_url("")
        assert result is None

    @pytest.mark.django_db
    def test_returns_url_for_local_storage(self, photo):
        """In dev (local storage), returns the regular media URL."""
        url = get_signed_url(photo.file)
        assert url is not None
        assert "photos/" in url


class TestPhotoModelIntegration:
    """Integration tests verifying Photo model works with storage utilities."""

    @pytest.mark.django_db
    def test_photo_upload_creates_file(self, photo):
        assert photo.file
        assert photo.file.name

    @pytest.mark.django_db
    def test_photo_file_url(self, photo):
        url = photo.file.url
        assert url is not None
