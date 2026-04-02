from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.apartments.models import Apartment
from apps.inspections.models import Inspection
from tests.factories import ApartmentFactory, InspectionFactory, OwnerFactory


@pytest.mark.django_db
class TestPurgeDeletedAccounts:
    @patch("apps.accounts.management.commands.purge_deleted_accounts.default_storage")
    def test_purges_expired_soft_deleted_accounts(self, mock_storage):
        user = OwnerFactory(deleted_at=timezone.now() - timedelta(days=31), is_active=False)
        call_command("purge_deleted_accounts")
        assert not User.objects.filter(pk=user.pk).exists()

    @patch("apps.accounts.management.commands.purge_deleted_accounts.default_storage")
    def test_keeps_recently_soft_deleted_accounts(self, mock_storage):
        user = OwnerFactory(deleted_at=timezone.now() - timedelta(days=15), is_active=False)
        call_command("purge_deleted_accounts")
        assert User.objects.filter(pk=user.pk).exists()

    @patch("apps.accounts.management.commands.purge_deleted_accounts.default_storage")
    def test_does_not_touch_active_accounts(self, mock_storage):
        user = OwnerFactory(is_active=True)
        call_command("purge_deleted_accounts")
        assert User.objects.filter(pk=user.pk).exists()

    @patch("apps.accounts.management.commands.purge_deleted_accounts.default_storage")
    def test_cascades_to_apartments_and_inspections(self, mock_storage):
        user = OwnerFactory(deleted_at=timezone.now() - timedelta(days=31), is_active=False)
        apartment = ApartmentFactory(owner=user)
        inspection = InspectionFactory(apartment=apartment)
        call_command("purge_deleted_accounts")
        assert not Apartment.objects.filter(pk=apartment.pk).exists()
        assert not Inspection.objects.filter(pk=inspection.pk).exists()

    @patch("apps.accounts.management.commands.purge_deleted_accounts.default_storage")
    def test_dry_run_does_not_purge(self, mock_storage):
        user = OwnerFactory(deleted_at=timezone.now() - timedelta(days=31), is_active=False)
        call_command("purge_deleted_accounts", "--dry-run")
        assert User.objects.filter(pk=user.pk).exists()

    @patch("apps.accounts.management.commands.purge_deleted_accounts.default_storage")
    def test_no_accounts_to_purge(self, mock_storage, capsys):
        call_command("purge_deleted_accounts")
        output = capsys.readouterr().out
        assert "Keine" in output
