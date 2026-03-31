import datetime

from django.utils import timezone

from apps.inspections.models import Inspection, InspectionItem, Photo
from tests.factories import (
    ApartmentFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    PhotoFactory,
)


class TestInspectionModel:
    def test_create(self, inspection):
        assert inspection.pk is not None
        assert inspection.status == Inspection.Status.SCHEDULED

    def test_str(self, inspection):
        result = str(inspection)
        assert str(inspection.pk) in result
        assert inspection.apartment.address in result
        assert "Geplant" in result

    def test_relationships(self, inspection):
        assert inspection.apartment is not None
        assert inspection.inspector is not None
        assert inspection.inspector.is_inspector

    def test_status_choices(self):
        assert Inspection.Status.SCHEDULED == "scheduled"
        assert Inspection.Status.IN_PROGRESS == "in_progress"
        assert Inspection.Status.COMPLETED == "completed"
        assert Inspection.Status.CANCELLED == "cancelled"

    def test_overall_rating_choices(self):
        assert Inspection.OverallRating.OK == "ok"
        assert Inspection.OverallRating.ATTENTION == "attention"
        assert Inspection.OverallRating.URGENT == "urgent"

    def test_nullable_datetime_fields(self, inspection):
        assert inspection.started_at is None
        assert inspection.completed_at is None

    def test_overall_rating_blank_by_default(self, inspection):
        assert inspection.overall_rating == ""

    def test_ordering(self, db):
        inspector = InspectorFactory()
        apt = ApartmentFactory()
        now = timezone.now()
        i1 = InspectionFactory(apartment=apt, inspector=inspector, scheduled_at=now - datetime.timedelta(days=1))
        i2 = InspectionFactory(apartment=apt, inspector=inspector, scheduled_at=now)
        inspections = list(Inspection.objects.all())
        assert inspections[0] == i2  # Most recent scheduled_at first
        assert inspections[1] == i1

    def test_related_name_apartment(self, inspection):
        assert inspection in inspection.apartment.inspections.all()

    def test_related_name_inspector(self, inspection):
        assert inspection in inspection.inspector.inspections.all()

    def test_cascade_delete_apartment(self, db, inspection):
        apt = inspection.apartment
        apt.delete()
        assert Inspection.objects.filter(pk=inspection.pk).count() == 0

    def test_cascade_delete_inspector(self, db, inspection):
        inspector = inspection.inspector
        inspector.delete()
        assert Inspection.objects.filter(pk=inspection.pk).count() == 0

    def test_general_notes_blank(self, inspection):
        assert inspection.general_notes == ""


class TestInspectionItemModel:
    def test_create(self, inspection_item):
        assert inspection_item.pk is not None
        assert inspection_item.result == InspectionItem.Result.OK

    def test_str(self, inspection_item):
        result = str(inspection_item)
        assert inspection_item.checklist_label in result
        assert "OK" in result

    def test_result_choices(self):
        assert InspectionItem.Result.OK == "ok"
        assert InspectionItem.Result.FLAGGED == "flagged"
        assert InspectionItem.Result.NA == "na"

    def test_severity_choices(self):
        assert InspectionItem.Severity.NONE == "none"
        assert InspectionItem.Severity.LOW == "low"
        assert InspectionItem.Severity.MEDIUM == "medium"
        assert InspectionItem.Severity.HIGH == "high"
        assert InspectionItem.Severity.URGENT == "urgent"

    def test_default_severity(self, inspection_item):
        assert inspection_item.severity == InspectionItem.Severity.NONE

    def test_ordering(self, db, inspection):
        item1 = InspectionItemFactory(inspection=inspection, order=2)
        item2 = InspectionItemFactory(inspection=inspection, order=1)
        items = list(InspectionItem.objects.filter(inspection=inspection))
        assert items[0] == item2  # Lower order first
        assert items[1] == item1

    def test_related_name(self, inspection_item):
        assert inspection_item in inspection_item.inspection.items.all()

    def test_cascade_delete_inspection(self, db, inspection_item):
        inspection = inspection_item.inspection
        inspection.delete()
        assert InspectionItem.objects.filter(pk=inspection_item.pk).count() == 0

    def test_notes_blank(self, inspection_item):
        assert inspection_item.notes == ""

    def test_german_characters_in_label(self, db, inspection):
        item = InspectionItemFactory(
            inspection=inspection,
            checklist_label="Kühlschrank Temperatur überprüfen",
            category="Küche",
        )
        item.refresh_from_db()
        assert item.checklist_label == "Kühlschrank Temperatur überprüfen"
        assert item.category == "Küche"


class TestPhotoModel:
    def test_create(self, photo):
        assert photo.pk is not None
        assert photo.file is not None

    def test_str(self, photo):
        result = str(photo)
        assert str(photo.pk) in result
        assert photo.caption in result

    def test_str_without_caption(self, db, inspection):
        photo = PhotoFactory(inspection=inspection, caption="")
        assert "Kein Titel" in str(photo)

    def test_inspection_item_nullable(self, photo):
        assert photo.inspection_item is None

    def test_with_inspection_item(self, db, inspection_item):
        photo = PhotoFactory(inspection=inspection_item.inspection, inspection_item=inspection_item)
        assert photo.inspection_item == inspection_item

    def test_related_name_inspection(self, photo):
        assert photo in photo.inspection.photos.all()

    def test_related_name_inspection_item(self, db, inspection_item):
        photo = PhotoFactory(inspection=inspection_item.inspection, inspection_item=inspection_item)
        assert photo in inspection_item.photos.all()

    def test_cascade_delete_inspection(self, db, photo):
        inspection = photo.inspection
        inspection.delete()
        assert Photo.objects.filter(pk=photo.pk).count() == 0

    def test_taken_at_nullable(self, photo):
        assert photo.taken_at is None

    def test_ordering(self, db, inspection):
        p1 = PhotoFactory(inspection=inspection)
        p2 = PhotoFactory(inspection=inspection)
        photos = list(Photo.objects.filter(inspection=inspection))
        assert photos[0] == p2  # Most recent created_at first
        assert photos[1] == p1
