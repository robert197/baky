from decimal import Decimal

from tests.factories import ApartmentFactory


class TestStructuredAddressFields:
    def test_create_with_structured_address(self, db):
        apt = ApartmentFactory(
            address="Musterstraße 1, 1010 Wien",
            street="Musterstraße 1",
            zip_code="1010",
            city="Wien",
        )
        apt.refresh_from_db()
        assert apt.street == "Musterstraße 1"
        assert apt.zip_code == "1010"
        assert apt.city == "Wien"

    def test_structured_fields_optional(self, db):
        apt = ApartmentFactory(street="", zip_code="", city="")
        assert apt.street == ""
        assert apt.zip_code == ""

    def test_city_defaults_to_wien(self, db):
        apt = ApartmentFactory()
        assert apt.city == "Wien"

    def test_latitude_longitude_nullable(self, db):
        apt = ApartmentFactory(latitude=None, longitude=None)
        assert apt.latitude is None
        assert apt.longitude is None

    def test_latitude_longitude_stored(self, db):
        apt = ApartmentFactory(
            latitude=Decimal("48.208176"),
            longitude=Decimal("16.373819"),
        )
        apt.refresh_from_db()
        assert apt.latitude == Decimal("48.208176")
        assert apt.longitude == Decimal("16.373819")

    def test_german_umlauts_in_street(self, db):
        apt = ApartmentFactory(street="Grünbergstraße 42")
        apt.refresh_from_db()
        assert apt.street == "Grünbergstraße 42"

    def test_zip_code_max_length(self, db):
        apt = ApartmentFactory(zip_code="1234567890")
        assert len(apt.zip_code) == 10


class TestMapsUrl:
    def test_maps_url_with_coordinates(self, db):
        apt = ApartmentFactory(
            latitude=Decimal("48.208176"),
            longitude=Decimal("16.373819"),
        )
        assert "48.208176" in apt.maps_url
        assert "16.373819" in apt.maps_url
        assert "google.com/maps" in apt.maps_url

    def test_maps_url_without_coordinates(self, db):
        apt = ApartmentFactory(
            address="Musterstraße 1, 1010 Wien",
            latitude=None,
            longitude=None,
        )
        assert "google.com/maps" in apt.maps_url
        assert "Musterstra" in apt.maps_url

    def test_maps_url_encodes_special_characters(self, db):
        apt = ApartmentFactory(
            address="Grünbergstraße 42, 1120 Wien",
            latitude=None,
            longitude=None,
        )
        url = apt.maps_url
        assert "google.com/maps" in url
        # URL should be encoded (no raw umlauts)
        assert "ü" not in url or "Gr%C3%BCnbergstra" in url

    def test_maps_url_prefers_coordinates(self, db):
        apt = ApartmentFactory(
            address="Musterstraße 1, 1010 Wien",
            latitude=Decimal("48.208176"),
            longitude=Decimal("16.373819"),
        )
        url = apt.maps_url
        assert "48.208176" in url
        assert "Musterstra" not in url
