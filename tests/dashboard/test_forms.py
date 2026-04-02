import pytest

from apps.dashboard.forms import (
    ApartmentEditForm,
    ExtraInspectionForm,
    PlanChangeRequestForm,
    SubscriptionActionForm,
)
from tests.factories import ApartmentFactory, OwnerFactory


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


@pytest.mark.django_db
class TestPlanChangeRequestForm:
    def test_valid_plan_change(self):
        form = PlanChangeRequestForm(data={"requested_plan": "premium", "message": "Upgrade bitte"})
        assert form.is_valid()

    def test_plan_required(self):
        form = PlanChangeRequestForm(data={"requested_plan": "", "message": ""})
        assert not form.is_valid()

    def test_message_optional(self):
        form = PlanChangeRequestForm(data={"requested_plan": "standard"})
        assert form.is_valid()

    def test_invalid_plan_choice(self):
        form = PlanChangeRequestForm(data={"requested_plan": "invalid"})
        assert not form.is_valid()


class TestSubscriptionActionForm:
    def test_valid_with_reason(self):
        form = SubscriptionActionForm(data={"reason": "Urlaub"})
        assert form.is_valid()

    def test_valid_without_reason(self):
        form = SubscriptionActionForm(data={})
        assert form.is_valid()

    def test_umlauts_in_reason(self):
        form = SubscriptionActionForm(data={"reason": "Längerer Aufenthalt im Ausland"})
        assert form.is_valid()


@pytest.mark.django_db
class TestExtraInspectionForm:
    def test_valid_form(self):
        apartment = ApartmentFactory()
        form = ExtraInspectionForm(
            data={"apartment": apartment.pk, "preferred_date": "2026-04-15", "notes": "Dringend"},
            owner=apartment.owner,
        )
        assert form.is_valid()

    def test_apartment_required(self):
        owner = OwnerFactory()
        form = ExtraInspectionForm(data={"preferred_date": "2026-04-15"}, owner=owner)
        assert not form.is_valid()

    def test_preferred_date_required(self):
        apartment = ApartmentFactory()
        form = ExtraInspectionForm(
            data={"apartment": apartment.pk},
            owner=apartment.owner,
        )
        assert not form.is_valid()

    def test_only_own_apartments(self):
        apartment = ApartmentFactory()
        other_owner = OwnerFactory()
        form = ExtraInspectionForm(
            data={"apartment": apartment.pk, "preferred_date": "2026-04-15"},
            owner=other_owner,
        )
        assert not form.is_valid()

    def test_notes_optional(self):
        apartment = ApartmentFactory()
        form = ExtraInspectionForm(
            data={"apartment": apartment.pk, "preferred_date": "2026-04-15"},
            owner=apartment.owner,
        )
        assert form.is_valid()
