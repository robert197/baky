"""Tests for the checklist template system (issue #10).

Covers: JSON validation, auto-copy on apartment creation,
default template loading, and customization.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.apartments.models import Apartment, ChecklistTemplate
from apps.inspections.checklist_defaults import get_default_checklist_items
from tests.factories import ApartmentFactory, OwnerFactory


class TestChecklistItemsValidation:
    """ChecklistTemplate.items must conform to the expected JSON schema."""

    def test_valid_items_accepted(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Küche",
                "label": "Herd sauber",
                "allowed_results": ["ok", "flagged"],
                "order": 1,
            },
        ]
        template.full_clean()  # Should not raise

    def test_items_with_na_result_accepted(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Geräte",
                "label": "Waschmaschine",
                "allowed_results": ["ok", "flagged", "na"],
                "order": 1,
            },
        ]
        template.full_clean()  # Should not raise

    def test_empty_items_accepted(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = []
        template.full_clean()  # Should not raise

    def test_items_must_be_list(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = {"not": "a list"}
        with pytest.raises(ValidationError, match="items.*list"):
            template.full_clean()

    def test_item_missing_category_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "label": "Test",
                "allowed_results": ["ok", "flagged"],
                "order": 1,
            },
        ]
        with pytest.raises(ValidationError, match="category"):
            template.full_clean()

    def test_item_missing_label_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "allowed_results": ["ok", "flagged"],
                "order": 1,
            },
        ]
        with pytest.raises(ValidationError, match="label"):
            template.full_clean()

    def test_item_missing_allowed_results_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "order": 1,
            },
        ]
        with pytest.raises(ValidationError, match="allowed_results"):
            template.full_clean()

    def test_item_missing_order_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "allowed_results": ["ok", "flagged"],
            },
        ]
        with pytest.raises(ValidationError, match="order"):
            template.full_clean()

    def test_invalid_allowed_result_value_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "allowed_results": ["ok", "invalid"],
                "order": 1,
            },
        ]
        with pytest.raises(ValidationError, match="allowed_results"):
            template.full_clean()

    def test_allowed_results_must_be_list(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "allowed_results": "ok",
                "order": 1,
            },
        ]
        with pytest.raises(ValidationError, match="allowed_results"):
            template.full_clean()

    def test_order_must_be_positive_integer(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "allowed_results": ["ok", "flagged"],
                "order": -1,
            },
        ]
        with pytest.raises(ValidationError, match="order"):
            template.full_clean()

    def test_item_not_a_dict_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = ["not a dict"]
        with pytest.raises(ValidationError):
            template.full_clean()

    def test_empty_allowed_results_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "allowed_results": [],
                "order": 1,
            },
        ]
        with pytest.raises(ValidationError, match="allowed_results"):
            template.full_clean()

    def test_boolean_order_rejected(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Test",
                "label": "Test",
                "allowed_results": ["ok", "flagged"],
                "order": True,
            },
        ]
        with pytest.raises(ValidationError, match="order"):
            template.full_clean()

    def test_german_characters_in_labels(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items = [
            {
                "category": "Küche",
                "label": "Kühlschrank sauber und funktionsfähig",
                "allowed_results": ["ok", "flagged"],
                "order": 1,
            },
        ]
        template.full_clean()  # Should not raise


class TestAutoCreateChecklistTemplate:
    """New apartments automatically get a ChecklistTemplate with default items."""

    def test_apartment_creation_creates_checklist_template(self, db):
        owner = OwnerFactory()
        apartment = Apartment.objects.create(
            owner=owner,
            address="Teststraße 1, 1010 Wien",
        )
        assert hasattr(apartment, "checklist_template")
        assert apartment.checklist_template is not None

    def test_auto_template_has_default_items(self, db):
        owner = OwnerFactory()
        apartment = Apartment.objects.create(
            owner=owner,
            address="Teststraße 1, 1010 Wien",
        )
        default_items = get_default_checklist_items()
        assert apartment.checklist_template.items == default_items

    def test_auto_template_has_22_items(self, db):
        owner = OwnerFactory()
        apartment = Apartment.objects.create(
            owner=owner,
            address="Teststraße 1, 1010 Wien",
        )
        assert len(apartment.checklist_template.items) == 22

    def test_auto_template_name_includes_address(self, db):
        owner = OwnerFactory()
        apartment = Apartment.objects.create(
            owner=owner,
            address="Grünbergstraße 42, 1120 Wien",
        )
        assert "Grünbergstraße 42" in apartment.checklist_template.name

    def test_no_duplicate_template_on_save(self, db):
        owner = OwnerFactory()
        apartment = Apartment.objects.create(
            owner=owner,
            address="Teststraße 1, 1010 Wien",
        )
        # Save again — should not create a second template
        apartment.address = "Neue Adresse 2, 1020 Wien"
        apartment.save()
        assert ChecklistTemplate.objects.filter(apartment=apartment).count() == 1

    def test_factory_created_apartment_gets_template(self, db):
        apartment = ApartmentFactory()
        assert hasattr(apartment, "checklist_template")
        assert apartment.checklist_template is not None


class TestChecklistTemplateCustomization:
    """Owners can customize their apartment's checklist."""

    def test_add_item(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        new_item = {
            "category": "Spezial",
            "label": "Pool überprüft",
            "allowed_results": ["ok", "flagged", "na"],
            "order": len(template.items) + 1,
        }
        template.items.append(new_item)
        template.save()
        template.refresh_from_db()
        assert template.items[-1]["label"] == "Pool überprüft"

    def test_remove_item(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        original_count = len(template.items)
        template.items = template.items[:-1]
        template.save()
        template.refresh_from_db()
        assert len(template.items) == original_count - 1

    def test_reorder_items(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        # Reverse the list and reassign sequential order values
        reversed_items = list(reversed(template.items))
        for i, item in enumerate(reversed_items):
            item["order"] = i + 1
        template.items = reversed_items
        template.save()
        template.refresh_from_db()
        # First item in the reversed list was originally the last
        assert template.items[0]["category"] == "Nach der Reinigung"
        assert template.items[0]["order"] == 1

    def test_modify_item_label(self, db):
        apartment = ApartmentFactory()
        template = apartment.checklist_template
        template.items[0]["label"] = "Geändertes Label"
        template.save()
        template.refresh_from_db()
        assert template.items[0]["label"] == "Geändertes Label"

    def test_each_apartment_has_independent_template(self, db):
        owner = OwnerFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)

        # Modify apt1's template
        apt1.checklist_template.items = []
        apt1.checklist_template.save()

        # apt2's template should be unaffected
        apt2.checklist_template.refresh_from_db()
        assert len(apt2.checklist_template.items) == 22


class TestDefaultChecklistIntegration:
    """The default checklist fixture is correctly loaded into templates."""

    def test_default_items_have_correct_schema(self, db):
        apartment = ApartmentFactory()
        for item in apartment.checklist_template.items:
            assert "category" in item
            assert "label" in item
            assert "allowed_results" in item
            assert "order" in item
            assert isinstance(item["allowed_results"], list)
            assert isinstance(item["order"], int)

    def test_default_items_cover_all_categories(self, db):
        apartment = ApartmentFactory()
        categories = {item["category"] for item in apartment.checklist_template.items}
        expected = {
            "Allgemeiner Eindruck",
            "Küche",
            "Badezimmer",
            "Wohnbereiche",
            "Geräte",
            "Schlafzimmer",
            "Zugang & Sicherheit",
            "Nach der Reinigung",
        }
        assert categories == expected

    def test_default_items_have_sequential_order(self, db):
        apartment = ApartmentFactory()
        orders = [item["order"] for item in apartment.checklist_template.items]
        assert orders == list(range(1, 23))

    def test_default_items_allowed_results_valid(self, db):
        apartment = ApartmentFactory()
        valid_values = {"ok", "flagged", "na"}
        for item in apartment.checklist_template.items:
            for result in item["allowed_results"]:
                assert result in valid_values
