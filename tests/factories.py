import datetime

import factory
from django.utils import timezone

from apps.accounts.models import Subscription, User
from apps.apartments.models import Apartment, ChecklistTemplate
from apps.inspections.models import Inspection, InspectionItem, Photo
from apps.reports.models import Report


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    role = User.Role.OWNER

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "testpass123")
        if create:
            self.save(update_fields=["password"])


class InspectorFactory(UserFactory):
    role = User.Role.INSPECTOR


class AdminFactory(UserFactory):
    role = User.Role.ADMIN


# Alias for readability — UserFactory already defaults to OWNER
OwnerFactory = UserFactory


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    owner = factory.SubFactory(OwnerFactory)
    address = factory.Sequence(lambda n: f"Musterstraße {n}, 1010 Wien")
    street = factory.Sequence(lambda n: f"Musterstraße {n}")
    zip_code = "1010"
    city = "Wien"
    latitude = None
    longitude = None
    access_method = Apartment.AccessMethod.KEY_HANDOVER
    access_code = ""
    access_notes = "Schlüssel beim Portier"
    special_instructions = ""
    status = Apartment.Status.ACTIVE


class ChecklistTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ChecklistTemplate
        django_get_or_create = ("apartment",)

    apartment = factory.SubFactory(ApartmentFactory)
    name = factory.LazyAttribute(lambda obj: f"Checkliste — {obj.apartment.address}")
    items = factory.LazyFunction(
        lambda: [
            {"category": "Eingang", "label": "Tür schließt korrekt", "allowed_results": ["ok", "flagged"], "order": 1},
            {"category": "Küche", "label": "Herd sauber", "allowed_results": ["ok", "flagged"], "order": 2},
            {"category": "Bad", "label": "Keine Wasserschäden", "allowed_results": ["ok", "flagged"], "order": 3},
        ]
    )


class InspectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Inspection

    apartment = factory.SubFactory(ApartmentFactory)
    inspector = factory.SubFactory(InspectorFactory)
    scheduled_at = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=1))
    status = Inspection.Status.SCHEDULED


class InspectionItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InspectionItem

    inspection = factory.SubFactory(InspectionFactory)
    checklist_label = "Tür schließt korrekt"
    category = "Eingang"
    result = InspectionItem.Result.OK
    severity = InspectionItem.Severity.NONE
    order = factory.Sequence(lambda n: n)


class PhotoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Photo

    inspection = factory.SubFactory(InspectionFactory)
    inspection_item = None
    file = factory.django.ImageField(filename="test_photo.jpg")
    caption = "Testfoto"


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Report

    inspection = factory.SubFactory(
        InspectionFactory, status=Inspection.Status.COMPLETED, completed_at=factory.LazyFunction(timezone.now)
    )
    status = Report.Status.COMPLETED
    html_content = "<h1>Inspektionsbericht</h1><p>Testbericht</p>"
    generated_at = factory.LazyFunction(lambda: timezone.now())


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    owner = factory.SubFactory(OwnerFactory)
    plan = Subscription.Plan.BASIS
    status = Subscription.Status.ACTIVE
    started_at = factory.LazyFunction(lambda: datetime.date.today())
    billing_cycle = Subscription.BillingCycle.MONTHLY
