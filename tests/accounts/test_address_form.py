from apps.accounts.forms import ApartmentOnboardingForm


class TestApartmentOnboardingFormAddressFields:
    def test_valid_with_structured_address(self, db):
        data = {
            "address": "Musterstraße 1, 1010 Wien",
            "street": "Musterstraße 1",
            "zip_code": "1010",
            "city": "Wien",
            "latitude": "48.208176",
            "longitude": "16.373819",
            "access_method": "key_handover",
        }
        form = ApartmentOnboardingForm(data=data)
        assert form.is_valid(), form.errors

    def test_valid_without_structured_address(self, db):
        """Manual fallback: only address text, no structured fields."""
        data = {
            "address": "Musterstraße 1/5, 1010 Wien",
            "street": "",
            "zip_code": "",
            "city": "",
            "latitude": "",
            "longitude": "",
            "access_method": "key_handover",
        }
        form = ApartmentOnboardingForm(data=data)
        assert form.is_valid(), form.errors

    def test_structured_fields_are_hidden_inputs(self, db):
        form = ApartmentOnboardingForm()
        assert form.fields["street"].widget.input_type == "hidden"
        assert form.fields["zip_code"].widget.input_type == "hidden"
        assert form.fields["city"].widget.input_type == "hidden"
        assert form.fields["latitude"].widget.input_type == "hidden"
        assert form.fields["longitude"].widget.input_type == "hidden"

    def test_address_field_has_autocomplete_off(self, db):
        form = ApartmentOnboardingForm()
        assert form.fields["address"].widget.attrs.get("autocomplete") == "off"

    def test_form_saves_structured_data(self, db):
        from tests.factories import OwnerFactory

        data = {
            "address": "Grünbergstraße 42, 1120 Wien",
            "street": "Grünbergstraße 42",
            "zip_code": "1120",
            "city": "Wien",
            "latitude": "48.175043",
            "longitude": "16.325890",
            "access_method": "lockbox",
            "access_code": "5678",
        }
        form = ApartmentOnboardingForm(data=data)
        assert form.is_valid()
        apartment = form.save(commit=False)
        apartment.owner = OwnerFactory()
        apartment.save()

        apartment.refresh_from_db()
        assert apartment.street == "Grünbergstraße 42"
        assert apartment.zip_code == "1120"
        assert apartment.city == "Wien"
        assert str(apartment.latitude) == "48.175043"
        assert str(apartment.longitude) == "16.325890"

    def test_form_includes_all_address_fields(self, db):
        form = ApartmentOnboardingForm()
        assert "street" in form.fields
        assert "zip_code" in form.fields
        assert "city" in form.fields
        assert "latitude" in form.fields
        assert "longitude" in form.fields
