import logging

from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.inspections.models import Photo

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Photo)
def delete_photo_files_from_storage(sender, instance, **kwargs):
    """Delete S3 files when a Photo record is deleted (GDPR compliance)."""
    for field_name in ("file", "thumbnail"):
        field_file = getattr(instance, field_name, None)
        if field_file and field_file.name:
            try:
                default_storage.delete(field_file.name)
            except Exception:
                logger.warning("Failed to delete %s for Photo %s", field_file.name, instance.pk)
