import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestImpressumPage:
    """Tests for the Impressum (legal notice) page at /impressum/."""

    def test_get_success(self, client: Client):
        response = client.get(reverse("public:impressum"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client: Client):
        response = client.get(reverse("public:impressum"))
        assert "public/impressum.html" in [t.name for t in response.templates]

    def test_url_is_german(self, client: Client):
        response = client.get("/impressum/")
        assert response.status_code == 200

    def test_no_auth_required(self, client: Client):
        response = client.get(reverse("public:impressum"))
        assert response.status_code == 200

    def test_page_title_contains_impressum(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert "Impressum" in content

    def test_company_info_section(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert "Angaben gemäß" in content or "Firmenname" in content or "BAKY" in content

    def test_contact_section(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert "Kontakt" in content or "E-Mail" in content

    def test_responsible_person_section(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert "Verantwortlich" in content or "Geschäftsführ" in content

    def test_placeholder_marked(self, client: Client):
        """Placeholder content should be clearly marked for legal review."""
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert "[" in content or "PLATZHALTER" in content or "placeholder" in content.lower()

    def test_german_language(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert 'lang="de-AT"' in content

    def test_footer_links_present(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert "/datenschutz/" in content
        assert "/agb/" in content

    def test_mobile_responsive_meta(self, client: Client):
        response = client.get(reverse("public:impressum"))
        content = response.content.decode()
        assert 'name="viewport"' in content


@pytest.mark.django_db
class TestDatenschutzPage:
    """Tests for the Datenschutz (privacy policy) page at /datenschutz/."""

    def test_get_success(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        assert "public/datenschutz.html" in [t.name for t in response.templates]

    def test_url_is_german(self, client: Client):
        response = client.get("/datenschutz/")
        assert response.status_code == 200

    def test_no_auth_required(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        assert response.status_code == 200

    def test_page_title_contains_datenschutz(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "Datenschutz" in content

    def test_data_collection_section(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "Datenerhebung" in content or "Datenverarbeitung" in content or "erheben" in content

    def test_photo_handling_section(self, client: Client):
        """Privacy policy must cover photo documentation handling."""
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "Foto" in content or "Bild" in content

    def test_data_retention_section(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "Speicherdauer" in content or "Aufbewahrung" in content or "Löschung" in content

    def test_user_rights_section(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "Rechte" in content or "Auskunft" in content

    def test_placeholder_marked(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "[" in content or "PLATZHALTER" in content or "placeholder" in content.lower()

    def test_german_language(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert 'lang="de-AT"' in content

    def test_footer_links_present(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "/impressum/" in content
        assert "/agb/" in content

    def test_mobile_responsive_meta(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert 'name="viewport"' in content


@pytest.mark.django_db
class TestAGBPage:
    """Tests for the AGB (terms of service) page at /agb/."""

    def test_get_success(self, client: Client):
        response = client.get(reverse("public:agb"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client: Client):
        response = client.get(reverse("public:agb"))
        assert "public/agb.html" in [t.name for t in response.templates]

    def test_url_is_german(self, client: Client):
        response = client.get("/agb/")
        assert response.status_code == 200

    def test_no_auth_required(self, client: Client):
        response = client.get(reverse("public:agb"))
        assert response.status_code == 200

    def test_page_title_contains_agb(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "Allgemeine Geschäftsbedingungen" in content or "AGB" in content

    def test_service_description_section(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "Leistung" in content or "Inspektionsservice" in content

    def test_payment_terms_section(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "Zahlung" in content or "Vergütung" in content or "Preise" in content

    def test_liability_section(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "Haftung" in content

    def test_cancellation_section(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "Kündigung" in content or "Widerruf" in content

    def test_placeholder_marked(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "[" in content or "PLATZHALTER" in content or "placeholder" in content.lower()

    def test_german_language(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert 'lang="de-AT"' in content

    def test_footer_links_present(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert "/impressum/" in content
        assert "/datenschutz/" in content

    def test_mobile_responsive_meta(self, client: Client):
        response = client.get(reverse("public:agb"))
        content = response.content.decode()
        assert 'name="viewport"' in content


@pytest.mark.django_db
class TestCookieBanner:
    """Tests that the cookie banner is present on pages."""

    def test_cookie_banner_on_landing_page(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "cookie_dismissed" in content

    def test_cookie_banner_on_datenschutz(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "cookie_dismissed" in content

    def test_cookie_banner_text(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "technisch notwendige Cookies" in content


@pytest.mark.django_db
class TestDatenschutzRetentionPeriods:
    """Tests that datenschutz page has concrete retention periods."""

    def test_photo_retention_period(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "90 Tage" in content

    def test_account_deletion_grace_period(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "30 Tage" in content

    def test_data_export_mentioned(self, client: Client):
        response = client.get(reverse("public:datenschutz"))
        content = response.content.decode()
        assert "Datenexport" in content


@pytest.mark.django_db
class TestFooterLegalLinks:
    """Tests that footer links point to real legal pages."""

    def test_footer_impressum_link(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "/impressum/" in content

    def test_footer_datenschutz_link(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "/datenschutz/" in content

    def test_footer_agb_link(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "/agb/" in content
