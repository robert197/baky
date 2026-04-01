import uuid

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, OnboardingProgress, Subscription, User
from tests.factories import ApartmentFactory, InspectorFactory, UserFactory


@pytest.fixture
def client():
    return Client()


class TestSignupView:
    def test_get_signup_page(self, client, db):
        response = client.get("/accounts/signup/")
        assert response.status_code == 200
        assert "Konto erstellen" in response.content.decode()

    def test_signup_page_contains_form_fields(self, client, db):
        response = client.get("/accounts/signup/")
        content = response.content.decode()
        assert "Vorname" in content
        assert "Nachname" in content
        assert "E-Mail" in content
        assert "Telefonnummer" in content
        assert "Passwort" in content

    def test_signup_with_valid_data(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "phone": "+43 123 456789",
            "password1": "securePass123!",
            "password2": "securePass123!",
            "selected_plan": "basis",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 302
        assert response.url == "/accounts/onboarding/apartment/"

        user = User.objects.get(email="max@example.com")
        assert user.first_name == "Max"
        assert user.last_name == "Mustermann"
        assert user.role == User.Role.OWNER
        assert user.username == "max@example.com"
        assert user.check_password("securePass123!")

    def test_signup_creates_email_verification_token(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        client.post("/accounts/signup/", data)
        user = User.objects.get(email="max@example.com")
        assert EmailVerificationToken.objects.filter(user=user).exists()

    def test_signup_sends_verification_email(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        client.post("/accounts/signup/", data)
        assert len(mail.outbox) == 1
        assert "bestätigen" in mail.outbox[0].subject.lower()
        assert "max@example.com" in mail.outbox[0].to

    def test_signup_creates_onboarding_progress(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
            "selected_plan": "extra",
        }
        client.post("/accounts/signup/", data)
        user = User.objects.get(email="max@example.com")
        onboarding = OnboardingProgress.objects.get(user=user)
        assert onboarding.selected_plan == "extra"
        assert onboarding.current_step == OnboardingProgress.Step.APARTMENT

    def test_signup_logs_user_in(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        client.post("/accounts/signup/", data)
        response = client.get("/accounts/onboarding/apartment/")
        assert response.status_code == 200

    def test_signup_with_plan_from_query_param(self, client, db):
        response = client.get("/accounts/signup/?plan=extra")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="extra"' in content

    def test_signup_with_duplicate_email(self, client, db):
        UserFactory(email="existing@example.com")
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "existing@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 200
        assert "bereits registriert" in response.content.decode()

    def test_signup_with_password_mismatch(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "differentPass456!",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 200
        assert "stimmen nicht überein" in response.content.decode()

    def test_signup_with_missing_required_fields(self, client, db):
        data = {
            "first_name": "",
            "last_name": "",
            "email": "",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 200
        assert User.objects.count() == 0

    def test_signup_with_short_password(self, client, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "short",
            "password2": "short",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 200
        assert User.objects.count() == 0

    def test_authenticated_user_redirected_from_signup(self, client, db):
        user = UserFactory()
        client.force_login(user)
        response = client.get("/accounts/signup/")
        assert response.status_code == 302

    def test_signup_email_case_insensitive(self, client, db):
        UserFactory(email="test@example.com")
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "TEST@EXAMPLE.COM",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 200
        assert "bereits registriert" in response.content.decode()

    def test_signup_with_german_characters(self, client, db):
        data = {
            "first_name": "Ännä",
            "last_name": "Müller-Strauß",
            "email": "anna@example.com",
            "phone": "+43 1 234 5678",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        response = client.post("/accounts/signup/", data)
        assert response.status_code == 302
        user = User.objects.get(email="anna@example.com")
        assert user.first_name == "Ännä"
        assert user.last_name == "Müller-Strauß"

    def test_login_page_links_to_signup(self, client, db):
        response = client.get("/accounts/login/")
        assert "/accounts/signup/" in response.content.decode()


class TestEmailVerificationView:
    def test_verify_valid_token(self, client, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        response = client.get(f"/accounts/verify/{token.token}/")
        assert response.status_code == 302
        token.refresh_from_db()
        assert token.is_verified

    def test_verify_already_verified_token(self, client, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user, verified_at=timezone.now())
        response = client.get(f"/accounts/verify/{token.token}/")
        assert response.status_code == 302

    def test_verify_expired_token(self, client, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        token.created_at = timezone.now() - timezone.timedelta(hours=49)
        token.save(update_fields=["created_at"])
        response = client.get(f"/accounts/verify/{token.token}/")
        assert response.status_code == 302
        token.refresh_from_db()
        assert not token.is_verified

    def test_verify_nonexistent_token(self, client, db):
        response = client.get(f"/accounts/verify/{uuid.uuid4()}/")
        assert response.status_code == 404

    def test_verify_redirects_authenticated_user_to_dashboard(self, client, db):
        user = UserFactory()
        client.force_login(user)
        token = EmailVerificationToken.objects.create(user=user)
        response = client.get(f"/accounts/verify/{token.token}/")
        assert response.status_code == 302
        assert "/accounts/redirect/" in response.url


class TestOnboardingApartmentView:
    def test_requires_authentication(self, client, db):
        response = client.get("/accounts/onboarding/apartment/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_requires_owner_role(self, client, db):
        user = InspectorFactory()
        client.force_login(user)
        response = client.get("/accounts/onboarding/apartment/")
        assert response.status_code == 404

    def test_get_apartment_form(self, client, db):
        user = UserFactory()
        client.force_login(user)
        response = client.get("/accounts/onboarding/apartment/")
        assert response.status_code == 200
        assert "Adresse der Wohnung" in response.content.decode()

    def test_submit_apartment_form(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Musterstraße 1/5, 1010 Wien",
            "access_method": "key_handover",
            "access_code": "",
            "access_notes": "Schlüssel beim Portier",
            "special_instructions": "",
        }
        response = client.post("/accounts/onboarding/apartment/", data)
        assert response.status_code == 302
        assert "/accounts/onboarding/checklist/" in response.url

        onboarding = OnboardingProgress.objects.get(user=user)
        assert onboarding.apartment is not None
        assert onboarding.apartment.address == "Musterstraße 1/5, 1010 Wien"
        assert onboarding.current_step == OnboardingProgress.Step.CHECKLIST

    def test_submit_apartment_form_htmx(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Musterstraße 1/5, 1010 Wien",
            "access_method": "key_handover",
        }
        response = client.post("/accounts/onboarding/apartment/", data, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "Checkliste" in response.content.decode()

    def test_apartment_auto_creates_checklist(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Musterstraße 1/5, 1010 Wien",
            "access_method": "key_handover",
        }
        client.post("/accounts/onboarding/apartment/", data)
        onboarding = OnboardingProgress.objects.get(user=user)
        assert hasattr(onboarding.apartment, "checklist_template")

    def test_submit_apartment_missing_address(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "",
            "access_method": "key_handover",
        }
        response = client.post("/accounts/onboarding/apartment/", data)
        assert response.status_code == 200

    def test_redirects_if_onboarding_complete(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user, is_complete=True)
        response = client.get("/accounts/onboarding/apartment/")
        assert response.status_code == 302
        assert "/dashboard/" in response.url

    def test_apartment_sets_owner_to_current_user(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        data = {
            "address": "Teststraße 5, 1020 Wien",
            "access_method": "lockbox",
            "access_code": "1234",
        }
        client.post("/accounts/onboarding/apartment/", data)
        onboarding = OnboardingProgress.objects.get(user=user)
        assert onboarding.apartment.owner == user


class TestOnboardingChecklistView:
    def test_requires_authentication(self, client, db):
        response = client.get("/accounts/onboarding/checklist/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_requires_owner_role(self, client, db):
        user = InspectorFactory()
        client.force_login(user)
        response = client.get("/accounts/onboarding/checklist/")
        assert response.status_code == 404

    def test_redirects_if_no_apartment(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        response = client.get("/accounts/onboarding/checklist/")
        assert response.status_code == 302
        assert "/accounts/onboarding/apartment/" in response.url

    def test_get_checklist_page(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=2)
        response = client.get("/accounts/onboarding/checklist/")
        assert response.status_code == 200
        assert "Checkliste anpassen" in response.content.decode()

    def test_checklist_shows_default_items(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=2)
        response = client.get("/accounts/onboarding/checklist/")
        content = response.content.decode()
        assert "enabled_items" in content

    def test_submit_checklist_with_selected_items(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        onboarding = OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=2)
        checklist = apartment.checklist_template
        first_label = checklist.items[0]["label"]
        data = {"enabled_items": [first_label]}
        response = client.post("/accounts/onboarding/checklist/", data)
        assert response.status_code == 302
        assert "/accounts/onboarding/plan/" in response.url

        checklist.refresh_from_db()
        assert len(checklist.items) == 1
        assert checklist.items[0]["label"] == first_label

        onboarding.refresh_from_db()
        assert onboarding.current_step == OnboardingProgress.Step.PLAN

    def test_submit_checklist_with_custom_items(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=2)
        checklist = apartment.checklist_template
        first_label = checklist.items[0]["label"]
        data = {
            "enabled_items": [first_label],
            "custom_items": "Balkonpflanzen gegossen\nBriefkasten geleert",
        }
        client.post("/accounts/onboarding/checklist/", data)
        checklist.refresh_from_db()
        assert len(checklist.items) == 3
        labels = [item["label"] for item in checklist.items]
        assert "Balkonpflanzen gegossen" in labels
        assert "Briefkasten geleert" in labels

    def test_custom_items_have_individuell_category(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=2)
        data = {
            "enabled_items": [],
            "custom_items": "Mein eigener Punkt",
        }
        client.post("/accounts/onboarding/checklist/", data)
        checklist = apartment.checklist_template
        checklist.refresh_from_db()
        custom = [item for item in checklist.items if item["label"] == "Mein eigener Punkt"]
        assert len(custom) == 1
        assert custom[0]["category"] == "Individuell"

    def test_submit_checklist_htmx(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=2)
        data = {"enabled_items": []}
        response = client.post("/accounts/onboarding/checklist/", data, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "Plan" in response.content.decode()


class TestOnboardingPlanView:
    def test_requires_authentication(self, client, db):
        response = client.get("/accounts/onboarding/plan/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_requires_owner_role(self, client, db):
        user = InspectorFactory()
        client.force_login(user)
        response = client.get("/accounts/onboarding/plan/")
        assert response.status_code == 404

    def test_redirects_if_no_apartment(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        response = client.get("/accounts/onboarding/plan/")
        assert response.status_code == 302
        assert "/accounts/onboarding/apartment/" in response.url

    def test_get_plan_selection_page(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=3)
        response = client.get("/accounts/onboarding/plan/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Plan auswählen" in content
        assert "59,90" in content
        assert "99,90" in content

    def test_submit_basis_plan(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=3)
        response = client.post("/accounts/onboarding/plan/", {"plan": "basis"})
        assert response.status_code == 302
        assert "/accounts/onboarding/confirmation/" in response.url

        sub = Subscription.objects.get(owner=user)
        assert sub.plan == "basis"
        assert sub.status == Subscription.Status.ACTIVE

    def test_submit_extra_plan(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=3)
        response = client.post("/accounts/onboarding/plan/", {"plan": "extra"})
        assert response.status_code == 302

        sub = Subscription.objects.get(owner=user)
        assert sub.plan == "extra"

    def test_submit_plan_htmx(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=3)
        response = client.post("/accounts/onboarding/plan/", {"plan": "basis"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "Fast geschafft" in response.content.decode()

    def test_submit_invalid_plan(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=3)
        response = client.post("/accounts/onboarding/plan/", {"plan": "invalid"})
        assert response.status_code == 200
        assert not Subscription.objects.filter(owner=user).exists()

    def test_plan_selection_preserves_initial_plan(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=3, selected_plan="extra")
        response = client.get("/accounts/onboarding/plan/")
        content = response.content.decode()
        assert "extra" in content


class TestOnboardingConfirmationView:
    def test_requires_authentication(self, client, db):
        response = client.get("/accounts/onboarding/confirmation/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_requires_owner_role(self, client, db):
        user = InspectorFactory()
        client.force_login(user)
        response = client.get("/accounts/onboarding/confirmation/")
        assert response.status_code == 404

    def test_redirects_if_no_apartment(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user)
        response = client.get("/accounts/onboarding/confirmation/")
        assert response.status_code == 302
        assert "/accounts/onboarding/apartment/" in response.url

    def test_get_confirmation_page(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=4, selected_plan="basis")
        response = client.get("/accounts/onboarding/confirmation/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Fast geschafft" in content
        assert apartment.address in content

    def test_confirmation_shows_plan_display(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=4, selected_plan="basis")
        response = client.get("/accounts/onboarding/confirmation/")
        assert "Basis" in response.content.decode()

    def test_confirmation_shows_checklist_count(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=4, selected_plan="basis")
        checklist_count = len(apartment.checklist_template.items)
        response = client.get("/accounts/onboarding/confirmation/")
        assert str(checklist_count) in response.content.decode()

    def test_submit_confirmation(self, client, db):
        user = UserFactory()
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=4, selected_plan="basis")
        response = client.post("/accounts/onboarding/confirmation/")
        assert response.status_code == 302
        assert "/dashboard/" in response.url

        onboarding = OnboardingProgress.objects.get(user=user)
        assert onboarding.is_complete

    def test_submit_confirmation_sends_welcome_email(self, client, db):
        user = UserFactory(first_name="Max")
        client.force_login(user)
        apartment = ApartmentFactory(owner=user)
        OnboardingProgress.objects.create(user=user, apartment=apartment, current_step=4, selected_plan="basis")
        client.post("/accounts/onboarding/confirmation/")
        assert len(mail.outbox) == 1
        assert "Willkommen" in mail.outbox[0].subject

    def test_redirects_if_onboarding_complete(self, client, db):
        user = UserFactory()
        client.force_login(user)
        OnboardingProgress.objects.create(user=user, is_complete=True)
        response = client.get("/accounts/onboarding/confirmation/")
        assert response.status_code == 302
        assert "/dashboard/" in response.url
