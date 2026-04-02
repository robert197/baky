from unittest.mock import patch

import pytest

from apps.inspections.models import Photo
from tests.factories import PhotoFactory


@pytest.mark.django_db
class TestPhotoDeleteSignal:
    @patch("apps.inspections.signals.default_storage")
    def test_photo_delete_removes_s3_files(self, mock_storage, photo):
        file_name = photo.file.name
        photo.delete()
        mock_storage.delete.assert_any_call(file_name)

    @patch("apps.inspections.signals.default_storage")
    def test_photo_delete_handles_missing_s3_file(self, mock_storage, photo):
        mock_storage.delete.side_effect = Exception("File not found")
        photo.delete()  # Should not raise
        assert not Photo.objects.filter(pk=photo.pk).exists()

    @patch("apps.inspections.signals.default_storage")
    def test_photo_delete_with_thumbnail(self, mock_storage):
        photo = PhotoFactory(thumbnail="thumbs/test.jpg")
        file_name = photo.file.name
        photo.delete()
        mock_storage.delete.assert_any_call(file_name)
        mock_storage.delete.assert_any_call("thumbs/test.jpg")

    @patch("apps.inspections.signals.default_storage")
    def test_photo_delete_without_thumbnail(self, mock_storage):
        photo = PhotoFactory()
        # Factory generates a thumbnail via model save, so clear it
        Photo.objects.filter(pk=photo.pk).update(thumbnail="")
        photo.refresh_from_db()
        file_name = photo.file.name
        photo.delete()
        # Should only delete the file, not the empty thumbnail
        mock_storage.delete.assert_called_once_with(file_name)
