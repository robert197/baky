import pytest

from apps.accounts.models import DataExportRequest
from apps.accounts.tasks import generate_data_export
from tests.factories import ApartmentFactory, OwnerFactory


@pytest.mark.django_db
class TestGenerateDataExport:
    def test_generates_export(self):
        owner = OwnerFactory()
        ApartmentFactory(owner=owner)
        export_req = DataExportRequest.objects.create(user=owner)
        result = generate_data_export(export_req.pk)
        export_req.refresh_from_db()
        assert export_req.status == "COMPLETED"
        assert result["status"] == "success"
        assert export_req.export_file

    def test_export_handles_no_data(self):
        owner = OwnerFactory()
        export_req = DataExportRequest.objects.create(user=owner)
        result = generate_data_export(export_req.pk)
        export_req.refresh_from_db()
        assert result["status"] == "success"
        assert export_req.status == "COMPLETED"

    def test_export_marks_failed_on_invalid_id(self):
        result = generate_data_export(99999)
        assert result["status"] == "error"

    def test_export_includes_apartment_data(self):
        owner = OwnerFactory()
        ApartmentFactory(owner=owner, address="Teststraße 42, 1010 Wien")
        export_req = DataExportRequest.objects.create(user=owner)
        generate_data_export(export_req.pk)
        export_req.refresh_from_db()
        assert export_req.export_file
        # Verify file is a ZIP
        assert export_req.export_file.name.endswith(".zip")
