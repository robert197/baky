"""Hard-delete user accounts that were soft-deleted more than 30 days ago.

Run daily via cron or Django-Q2 schedule:
    make manage CMD="purge_deleted_accounts"

Collects S3 file paths before cascading delete to prevent orphaned files.
"""

import logging
from datetime import timedelta

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import Photo

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Hard-delete user accounts that were soft-deleted more than 30 days ago"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be purged without purging")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30)
        expired_users = User.objects.filter(
            deleted_at__isnull=False,
            deleted_at__lt=cutoff,
            is_active=False,
        )
        count = expired_users.count()

        if count == 0:
            self.stdout.write("Keine abgelaufenen Konten zum Löschen.")
            return

        if options["dry_run"]:
            for user in expired_users:
                self.stdout.write(f"  Would purge: User ID {user.pk} (deleted at {user.deleted_at})")
            self.stdout.write(f"Would purge {count} accounts (dry run)")
            return

        # Collect S3 paths before cascade delete removes DB records
        for user in expired_users:
            s3_paths = list(
                Photo.objects.filter(inspection__apartment__owner=user)
                .exclude(file="")
                .values_list("file", "thumbnail")
            )

            # Delete user (cascades to apartments, inspections, photos, reports)
            user_pk = user.pk
            user.delete()
            logger.info("Purged account ID %s and all associated data", user_pk)

            # Clean up S3 files
            for file_path, thumb_path in s3_paths:
                for path in (file_path, thumb_path):
                    if path:
                        try:
                            default_storage.delete(path)
                        except Exception:
                            logger.warning("Failed to delete S3 file: %s", path)

        self.stdout.write(self.style.SUCCESS(f"{count} Konto/Konten endgültig gelöscht."))
