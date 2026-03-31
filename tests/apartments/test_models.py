import pytest
from django.db import IntegrityError

from apps.apartments.models import Apartment, ChecklistTemplate
from tests.factories import ApartmentFactory, ChecklistTemplateFactory, OwnerFactory


class TestApartmentModel:
    def test_create(self, apartment):
        assert apartment.pk is not None
        assert apartment.status == Apartment.Status.ACTIVE

    def test_str(self, apartment):
        result = str(apartment)
        assert apartment.address in result
        assert "Aktiv" in result

    def test_owner_relationship(self, apartment):
        assert apartment.owner is not None
        assert apartment.owner.is_owner

    def test_related_name(self, db, user):
        apt = ApartmentFactory(owner=user)
        assert apt in user.apartments.all()

    def test_access_method_choices(self):
        assert Apartment.AccessMethod.KEY_HANDOVER == "key_handover"
        assert Apartment.AccessMethod.LOCKBOX == "lockbox"
        assert Apartment.AccessMethod.SMART_LOCK == "smart_lock"

    def test_status_choices(self):
        assert Apartment.Status.ACTIVE == "active"
        assert Apartment.Status.PAUSED == "paused"
        assert Apartment.Status.ARCHIVED == "archived"

    def test_access_notes_encrypted(self, db):
        apt = ApartmentFactory(access_notes="Schlüsselbox Code: 1234")
        apt.refresh_from_db()
        assert apt.access_notes == "Schlüsselbox Code: 1234"

    def test_special_instructions_blank(self, db):
        apt = ApartmentFactory(special_instructions="")
        assert apt.special_instructions == ""

    def test_ordering(self, db):
        owner = OwnerFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        apts = list(Apartment.objects.filter(owner=owner))
        # Most recently created first
        assert apts[0] == apt2
        assert apts[1] == apt1

    def test_cascade_delete_owner(self, db, apartment):
        owner = apartment.owner
        owner.delete()
        assert Apartment.objects.filter(pk=apartment.pk).count() == 0

    def test_german_characters_in_address(self, db):
        apt = ApartmentFactory(address="Grünbergstraße 42, 1120 Wien")
        apt.refresh_from_db()
        assert apt.address == "Grünbergstraße 42, 1120 Wien"

    def test_address_max_length(self, db):
        long_address = "A" * 255
        apt = ApartmentFactory(address=long_address)
        assert len(apt.address) == 255


class TestChecklistTemplateModel:
    def test_create(self, checklist_template):
        assert checklist_template.pk is not None
        assert len(checklist_template.items) > 0

    def test_str(self, checklist_template):
        result = str(checklist_template)
        assert checklist_template.name in result
        assert checklist_template.apartment.address in result

    def test_one_template_per_apartment(self, db):
        owner = OwnerFactory()
        apartment = ApartmentFactory(owner=owner)
        # Signal already created one template
        assert ChecklistTemplate.objects.filter(apartment=apartment).count() == 1
        # Manually trying to create another should fail
        with pytest.raises(IntegrityError):
            ChecklistTemplate.objects.create(
                apartment=apartment,
                name="Duplicate",
                items=[],
            )

    def test_items_json_structure(self, checklist_template):
        for item in checklist_template.items:
            assert "category" in item
            assert "label" in item
            assert "allowed_results" in item
            assert "order" in item

    def test_auto_created_template_has_items(self, db, apartment):
        # The signal auto-creates a template with default items
        template = apartment.checklist_template
        assert len(template.items) > 0

    def test_related_name(self, db, apartment):
        template = ChecklistTemplateFactory(apartment=apartment)
        assert apartment.checklist_template == template

    def test_ordering(self, db):
        owner = OwnerFactory()
        apt1 = ApartmentFactory(owner=owner)
        apt2 = ApartmentFactory(owner=owner)
        t1 = apt1.checklist_template
        t2 = apt2.checklist_template
        t1.name = "B-Template"
        t1.save()
        t2.name = "A-Template"
        t2.save()
        templates = list(ChecklistTemplate.objects.all())
        assert templates[0] == t2  # Alphabetical by name
        assert templates[1] == t1

    def test_cascade_delete_apartment(self, db, checklist_template):
        apartment = checklist_template.apartment
        apartment.delete()
        assert ChecklistTemplate.objects.filter(pk=checklist_template.pk).count() == 0
