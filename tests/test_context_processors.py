from django.test import RequestFactory

from baky.context_processors import google_maps


class TestGoogleMapsContextProcessor:
    def test_returns_api_key(self, settings):
        settings.GOOGLE_MAPS_API_KEY = "test-key-abc"
        request = RequestFactory().get("/")
        ctx = google_maps(request)
        assert ctx == {"GOOGLE_MAPS_API_KEY": "test-key-abc"}

    def test_returns_empty_string_when_not_set(self, settings):
        settings.GOOGLE_MAPS_API_KEY = ""
        request = RequestFactory().get("/")
        ctx = google_maps(request)
        assert ctx == {"GOOGLE_MAPS_API_KEY": ""}
