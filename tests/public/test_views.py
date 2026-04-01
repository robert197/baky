import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestLandingPage:
    """Tests for the public landing page at /."""

    def test_get_success(self, client: Client):
        response = client.get(reverse("public:home"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client: Client):
        response = client.get(reverse("public:home"))
        assert "public/home.html" in [t.name for t in response.templates]

    def test_url_is_root(self, client: Client):
        response = client.get("/")
        assert response.status_code == 200

    def test_hero_section_present(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "Betreuung. Absicherung. Kontrolle. Your Home." in content

    def test_cta_links_to_contact(self, client: Client):
        """CTA links to contact/signup section (signup page not built yet)."""
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "#kontakt" in content or reverse("accounts:login") in content

    def test_problem_section_present(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        # Pain points for absentee owners
        assert "Keine Kontrolle" in content or "keine Kontrolle" in content

    def test_how_it_works_section(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "So funktioniert" in content

    def test_features_section(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "Fotodokumentation" in content

    def test_pricing_preview(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "59,90" in content

    def test_faq_section(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "Häufige Fragen" in content or "FAQ" in content

    def test_footer_present(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "Impressum" in content
        assert "Datenschutz" in content

    def test_mobile_responsive_meta(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert 'name="viewport"' in content

    def test_german_language(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert 'lang="de"' in content

    def test_seo_meta_description(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert 'name="description"' in content
        # Description should mention the service
        assert "Kurzzeitvermietung" in content or "Inspektion" in content

    def test_open_graph_tags(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert 'property="og:title"' in content
        assert 'property="og:description"' in content
        assert 'property="og:type"' in content

    def test_structured_data_present(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "application/ld+json" in content

    def test_no_auth_required(self, client: Client):
        """Landing page should be accessible without login."""
        response = client.get(reverse("public:home"))
        assert response.status_code == 200

    def test_navbar_present(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        assert "Startseite" in content
        assert "Preise" in content

    def test_social_proof_section(self, client: Client):
        response = client.get(reverse("public:home"))
        content = response.content.decode()
        # Testimonial section should exist (placeholders)
        assert "Vertrauen" in content or "Kunden" in content or "Eigentümer" in content
