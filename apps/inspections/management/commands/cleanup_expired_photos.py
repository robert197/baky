"""Delete inspection photos older than 90 days that are not flagged by owner.

Run daily via cron or Django-Q2 schedule:
    make manage CMD="cleanup_expired_photos"
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.inspections.models import Photo


class Command(BaseCommand):
    help = "Delete inspection photos older than 90 days that are not flagged by owner"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)
        expired = Photo.objects.filter(
            created_at__lt=cutoff,
            is_flagged=False,
        )
        count = expired.count()

        if options["dry_run"]:
            self.stdout.write(f"Would delete {count} expired photos (dry run)")
            return

        # Delete triggers post_delete signal which cleans up S3 files
        deleted, _ = expired.delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} abgelaufene Fotos gelöscht."))
