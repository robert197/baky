from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.inspections.models import Photo
from tests.factories import PhotoFactory


@pytest.mark.django_db
class TestCleanupExpiredPhotos:
    @patch("apps.inspections.signals.default_storage")
    def test_deletes_photos_older_than_90_days(self, mock_storage):
        old_photo = PhotoFactory()
        Photo.objects.filter(pk=old_photo.pk).update(created_at=timezone.now() - timedelta(days=91))
        recent_photo = PhotoFactory()
        Photo.objects.filter(pk=recent_photo.pk).update(created_at=timezone.now() - timedelta(days=30))

        call_command("cleanup_expired_photos")

        assert not Photo.objects.filter(pk=old_photo.pk).exists()
        assert Photo.objects.filter(pk=recent_photo.pk).exists()

    @patch("apps.inspections.signals.default_storage")
    def test_keeps_flagged_photos(self, mock_storage):
        old_flagged = PhotoFactory(is_flagged=True, flagged_at=timezone.now() - timedelta(days=10))
        Photo.objects.filter(pk=old_flagged.pk).update(created_at=timezone.now() - timedelta(days=91))

        call_command("cleanup_expired_photos")

        assert Photo.objects.filter(pk=old_flagged.pk).exists()

    @patch("apps.inspections.signals.default_storage")
    def test_deletes_unflagged_old_photos(self, mock_storage):
        photo = PhotoFactory(is_flagged=False)
        Photo.objects.filter(pk=photo.pk).update(created_at=timezone.now() - timedelta(days=200))

        call_command("cleanup_expired_photos")

        assert not Photo.objects.filter(pk=photo.pk).exists()

    @patch("apps.inspections.signals.default_storage")
    def test_dry_run_does_not_delete(self, mock_storage):
        old_photo = PhotoFactory()
        Photo.objects.filter(pk=old_photo.pk).update(created_at=timezone.now() - timedelta(days=91))

        call_command("cleanup_expired_photos", "--dry-run")

        assert Photo.objects.filter(pk=old_photo.pk).exists()

    @patch("apps.inspections.signals.default_storage")
    def test_outputs_deletion_count(self, mock_storage, capsys):
        p1 = PhotoFactory()
        p2 = PhotoFactory()
        Photo.objects.filter(pk__in=[p1.pk, p2.pk]).update(created_at=timezone.now() - timedelta(days=91))

        call_command("cleanup_expired_photos")

        output = capsys.readouterr().out
        assert "2" in output

    @patch("apps.inspections.signals.default_storage")
    def test_does_not_delete_photos_under_90_days(self, mock_storage):
        photo = PhotoFactory()
        Photo.objects.filter(pk=photo.pk).update(created_at=timezone.now() - timedelta(days=89))

        call_command("cleanup_expired_photos")

        assert Photo.objects.filter(pk=photo.pk).exists()
