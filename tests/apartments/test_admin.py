import pytest
from django.urls import reverse

from tests.factories import AdminFactory, ApartmentFactory, ChecklistTemplateFactory, InspectionFactory


@pytest.mark.django_db
class TestApartmentAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:apartments_apartment_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_changelist_shows_apartment(self, client):
        client.force_login(self.superuser)
        ApartmentFactory(address="Stephansplatz 1, 1010 Wien")
        url = reverse("admin:apartments_apartment_changelist")
        response = client.get(url)
        assert "Stephansplatz 1" in response.content.decode()

    def test_change_form_loads(self, client):
        client.force_login(self.superuser)
        apt = ApartmentFactory()
        url = reverse("admin:apartments_apartment_change", args=[apt.pk])
        response = client.get(url)
        assert response.status_code == 200

    def test_search_by_address(self, client):
        client.force_login(self.superuser)
        ApartmentFactory(address="Kärntner Straße 5, 1010 Wien")
        url = reverse("admin:apartments_apartment_changelist")
        response = client.get(url, {"q": "Kärntner"})
        assert response.status_code == 200
        assert "Kärntner" in response.content.decode()

    def test_filter_by_status(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:apartments_apartment_changelist")
        response = client.get(url, {"status": "active"})
        assert response.status_code == 200

    def test_last_inspection_date_with_completed_inspection(self):
        from django.db.models import Max, Q
        from django.utils import timezone

        from apps.apartments.models import Apartment

        apt = ApartmentFactory()
        InspectionFactory(apartment=apt, status="completed", completed_at=timezone.now())
        annotated = Apartment.objects.annotate(
            _last_inspection_date=Max("inspections__completed_at", filter=Q(inspections__status="completed"))
        ).get(pk=apt.pk)
        assert annotated._last_inspection_date is not None

    def test_last_inspection_date_without_inspection(self):
        from django.db.models import Max, Q

        from apps.apartments.models import Apartment

        apt = ApartmentFactory()
        annotated = Apartment.objects.annotate(
            _last_inspection_date=Max("inspections__completed_at", filter=Q(inspections__status="completed"))
        ).get(pk=apt.pk)
        assert annotated._last_inspection_date is None

    def test_checklist_template_inline_present(self, client):
        client.force_login(self.superuser)
        apt = ApartmentFactory()
        ChecklistTemplateFactory(apartment=apt)
        url = reverse("admin:apartments_apartment_change", args=[apt.pk])
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestChecklistTemplateAdmin:
    def setup_method(self):
        self.superuser = AdminFactory(is_staff=True, is_superuser=True)

    def test_changelist_loads(self, client):
        client.force_login(self.superuser)
        url = reverse("admin:apartments_checklisttemplate_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_search_by_name(self, client):
        client.force_login(self.superuser)
        ChecklistTemplateFactory(name="Standardcheckliste Küche")
        url = reverse("admin:apartments_checklisttemplate_changelist")
        response = client.get(url, {"q": "Küche"})
        assert response.status_code == 200
        assert "Küche" in response.content.decode()
