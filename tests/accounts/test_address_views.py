from apps.accounts.models import OnboardingProgress
from tests.factories import UserFactory


class TestOnboardingApartmentStructuredAddress:
    def test_submit_with_structured_address(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Grünbergstraße 42, 1120 Wien",
            "street": "Grünbergstraße 42",
            "zip_code": "1120",
            "city": "Wien",
            "latitude": "48.175043",
            "longitude": "16.325890",
            "access_method": "key_handover",
        }
        response = client.post("/accounts/onboarding/apartment/", data)
        assert response.status_code == 302

        onboarding = OnboardingProgress.objects.get(user=user)
        apartment = onboarding.apartment
        assert apartment.street == "Grünbergstraße 42"
        assert apartment.zip_code == "1120"
        assert apartment.city == "Wien"
        assert str(apartment.latitude) == "48.175043"

    def test_submit_without_structured_address_fallback(self, client, db):
        """Manual fallback: address only, no structured fields."""
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Musterstraße 1/5, 1010 Wien",
            "access_method": "key_handover",
        }
        response = client.post("/accounts/onboarding/apartment/", data)
        assert response.status_code == 302

        onboarding = OnboardingProgress.objects.get(user=user)
        apartment = onboarding.apartment
        assert apartment.address == "Musterstraße 1/5, 1010 Wien"
        assert apartment.street == ""
        assert apartment.latitude is None

    def test_apartment_form_renders_hidden_fields(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        response = client.get("/accounts/onboarding/apartment/")
        content = response.content.decode()
        assert 'id="id_street"' in content
        assert 'id="id_zip_code"' in content
        assert 'id="id_city"' in content
        assert 'id="id_latitude"' in content
        assert 'id="id_longitude"' in content

    def test_maps_url_available_on_apartment(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Musterstraße 1, 1010 Wien",
            "street": "Musterstraße 1",
            "zip_code": "1010",
            "city": "Wien",
            "latitude": "48.208176",
            "longitude": "16.373819",
            "access_method": "key_handover",
        }
        client.post("/accounts/onboarding/apartment/", data)
        onboarding = OnboardingProgress.objects.get(user=user)
        assert "google.com/maps" in onboarding.apartment.maps_url


class TestGoogleMapsContextProcessor:
    def test_api_key_in_context(self, client, db, settings):
        settings.GOOGLE_MAPS_API_KEY = "test-api-key-123"
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        response = client.get("/accounts/onboarding/apartment/")
        content = response.content.decode()
        assert "test-api-key-123" in content

    def test_no_api_key_shows_fallback(self, client, db, settings):
        settings.GOOGLE_MAPS_API_KEY = ""
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        response = client.get("/accounts/onboarding/apartment/")
        content = response.content.decode()
        assert "googleapis.com" not in content
