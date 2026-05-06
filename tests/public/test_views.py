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
        assert "alles selbst" in content or "Wir schauen" in content

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
        assert "€ 89" in content

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
        assert 'lang="de-AT"' in content

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


@pytest.mark.django_db
class TestPricingPage:
    """Tests for the pricing page at /preise/."""

    def test_get_success(self, client: Client):
        response = client.get(reverse("public:pricing"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client: Client):
        response = client.get(reverse("public:pricing"))
        assert "public/pricing.html" in [t.name for t in response.templates]

    def test_url_is_german(self, client: Client):
        response = client.get("/preise/")
        assert response.status_code == 200

    def test_no_auth_required(self, client: Client):
        """Pricing page should be accessible without login."""
        response = client.get(reverse("public:pricing"))
        assert response.status_code == 200

    def test_basis_tier_displayed(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Basis" in content
        assert "€ 89" in content
        assert "2 Inspektionen" in content

    def test_standard_tier_displayed(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Standard" in content
        assert "€ 149" in content
        assert "4 Inspektionen" in content

    def test_premium_tier_displayed(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Premium" in content
        assert "€ 249" in content
        assert "8 Inspektionen" in content

    def test_tiers_have_photo_documentation(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Fotodokumentation" in content

    def test_tiers_have_digital_reports(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Digitale Berichte" in content or "Berichte" in content

    def test_tiers_have_urgent_alerts(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Sofort-Meldungen" in content

    def test_cta_buttons_present(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        # CTAs should link to signup with plan pre-selected
        assert "?plan=basis" in content
        assert "?plan=standard" in content
        assert "?plan=premium" in content

    def test_per_apartment_clarification(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "pro Wohnung" in content or "Pro Wohnung" in content

    def test_faq_section_present(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Häufige Fragen" in content or "FAQ" in content

    def test_recommended_tier_highlighted(self, client: Client):
        """One tier should be marked as recommended."""
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Empfohlen" in content or "empfohlen" in content

    def test_page_title_contains_pricing(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "Preise" in content

    def test_navbar_pricing_link_active(self, client: Client):
        """Navbar should have a working link to pricing page."""
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert "/preise/" in content

    def test_mobile_responsive_meta(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert 'name="viewport"' in content

    def test_german_language(self, client: Client):
        response = client.get(reverse("public:pricing"))
        content = response.content.decode()
        assert 'lang="de-AT"' in content
