import pytest

from apps.dashboard.forms import ApartmentEditForm
from tests.factories import ApartmentFactory


@pytest.mark.django_db
class TestApartmentEditForm:
    def test_valid_form(self):
        apartment = ApartmentFactory()
        form = ApartmentEditForm(
            data={
                "address": "Teststrasse 1, 1010 Wien",
                "access_method": "lockbox",
                "access_code": "1234",
                "access_notes": "Im Hof links",
                "special_instructions": "",
                "status": "active",
            },
            instance=apartment,
        )
        assert form.is_valid()

    def test_required_fields(self):
        form = ApartmentEditForm(data={})
        assert not form.is_valid()
        assert "address" in form.errors

    def test_status_choices_exclude_archived(self):
        form = ApartmentEditForm()
        status_values = [c[0] for c in form.fields["status"].widget.choices]
        assert "active" in status_values
        assert "paused" in status_values
        assert "archived" not in status_values

    def test_german_labels(self):
        form = ApartmentEditForm()
        assert "Adresse" in form.fields["address"].label
        assert "Zugang" in form.fields["access_method"].label

    def test_umlauts_in_address(self):
        apartment = ApartmentFactory()
        form = ApartmentEditForm(
            data={
                "address": "Grünbergstraße 42, 1120 Wien",
                "access_method": "lockbox",
                "access_code": "",
                "access_notes": "",
                "special_instructions": "Schlüssel beim Nachbarn Müller",
                "status": "active",
            },
            instance=apartment,
        )
        assert form.is_valid()
