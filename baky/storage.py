"""Custom storage backends and photo processing utilities for BAKY."""

import io
import os
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

# Maximum upload size: 10 MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# Thumbnail dimensions (max)
THUMBNAIL_MAX_SIZE = (300, 300)

# Accepted image formats
ACCEPTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
ACCEPTED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
}


def validate_photo_file(file) -> None:
    """Validate photo file size and format."""
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(f"Dateigröße darf maximal {MAX_UPLOAD_SIZE // (1024 * 1024)} MB betragen.")

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ACCEPTED_EXTENSIONS:
        raise ValidationError(
            f"Nicht unterstütztes Dateiformat: {ext}. Erlaubt: {', '.join(sorted(ACCEPTED_EXTENSIONS))}"
        )


def generate_upload_path(instance, filename: str) -> str:
    """Generate a unique upload path for photos: photos/YYYY/MM/uuid.ext"""
    from django.utils import timezone

    now = timezone.now()
    ext = os.path.splitext(filename)[1].lower()
    # Convert HEIC/HEIF to .jpg since we convert to JPEG
    if ext in (".heic", ".heif"):
        ext = ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return f"photos/{now.year}/{now.month:02d}/{unique_name}"


def generate_thumbnail_path(instance, filename: str) -> str:
    """Generate a unique upload path for thumbnails: photos/thumbs/YYYY/MM/uuid.jpg"""
    from django.utils import timezone

    now = timezone.now()
    unique_name = f"{uuid.uuid4().hex}.jpg"
    return f"photos/thumbs/{now.year}/{now.month:02d}/{unique_name}"


_heif_registered = False


def convert_heic_to_jpeg(file) -> ContentFile:
    """Convert a HEIC/HEIF file to JPEG format."""
    global _heif_registered  # noqa: PLW0603
    if not _heif_registered:
        import pillow_heif

        pillow_heif.register_heif_opener()
        _heif_registered = True

    img = Image.open(file)
    img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    original_name = os.path.splitext(file.name)[0]
    return ContentFile(buffer.read(), name=f"{original_name}.jpg")


def create_thumbnail(file) -> ContentFile:
    """Create a JPEG thumbnail from an image file, max 300x300 maintaining aspect ratio."""
    file.seek(0)
    img = Image.open(file)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail(THUMBNAIL_MAX_SIZE, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    buffer.seek(0)

    return ContentFile(buffer.read(), name="thumbnail.jpg")


def get_signed_url(file_field, expiry: int = 86400) -> str | None:
    """Get a signed URL for a file field. Returns None if file doesn't exist.

    Args:
        file_field: Django ImageField/FileField instance
        expiry: URL expiry time in seconds (default: 24 hours)
    """
    if not file_field:
        return None

    storage = file_field.storage
    if hasattr(storage, "url"):
        # S3Boto3Storage supports passing parameters for signed URL generation
        if hasattr(storage, "querystring_auth"):
            return storage.url(file_field.name, expire=expiry)
        # Local filesystem — just return the regular URL
        return file_field.url
    return None
