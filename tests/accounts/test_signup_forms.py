from apps.accounts.forms import ApartmentOnboardingForm, PlanSelectionForm, SignupForm
from apps.accounts.models import User
from tests.factories import UserFactory


class TestSignupForm:
    def test_valid_data(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "phone": "+43 123 456789",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert form.is_valid()

    def test_save_creates_owner(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert form.is_valid()
        user = form.save()
        assert user.role == User.Role.OWNER
        assert user.username == "max@example.com"
        assert user.check_password("securePass123!")

    def test_required_fields(self, db):
        data = {
            "first_name": "",
            "last_name": "",
            "email": "",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert not form.is_valid()
        assert "first_name" in form.errors
        assert "last_name" in form.errors
        assert "email" in form.errors

    def test_password_mismatch(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "differentPass!",
        }
        form = SignupForm(data=data)
        assert not form.is_valid()
        assert "password2" in form.errors

    def test_duplicate_email(self, db):
        UserFactory(email="existing@example.com")
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "existing@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_email_normalized_to_lowercase(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "MAX@EXAMPLE.COM",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["email"] == "max@example.com"

    def test_short_password(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "short",
            "password2": "short",
        }
        form = SignupForm(data=data)
        assert not form.is_valid()
        assert "password1" in form.errors

    def test_phone_optional(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert form.is_valid()

    def test_german_labels(self, db):
        form = SignupForm()
        assert form.fields["first_name"].label == "Vorname"
        assert form.fields["last_name"].label == "Nachname"
        assert form.fields["email"].label == "E-Mail-Adresse"
        assert form.fields["phone"].label == "Telefonnummer"
        assert form.fields["password1"].label == "Passwort"
        assert form.fields["password2"].label == "Passwort bestätigen"

    def test_german_characters_in_name(self, db):
        data = {
            "first_name": "Ännä",
            "last_name": "Müller-Strauß",
            "email": "anna@example.com",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert form.is_valid()

    def test_invalid_email_format(self, db):
        data = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "not-an-email",
            "password1": "securePass123!",
            "password2": "securePass123!",
        }
        form = SignupForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors


class TestApartmentOnboardingForm:
    def test_valid_data(self, db):
        data = {
            "address": "Musterstraße 1/5, 1010 Wien",
            "access_method": "key_handover",
            "access_code": "",
            "access_notes": "Schlüssel beim Portier",
            "special_instructions": "",
        }
        form = ApartmentOnboardingForm(data=data)
        assert form.is_valid()

    def test_address_required(self, db):
        data = {
            "address": "",
            "access_method": "key_handover",
        }
        form = ApartmentOnboardingForm(data=data)
        assert not form.is_valid()
        assert "address" in form.errors

    def test_access_code_optional(self, db):
        data = {
            "address": "Test 1, 1010 Wien",
            "access_method": "key_handover",
        }
        form = ApartmentOnboardingForm(data=data)
        assert form.is_valid()

    def test_german_labels(self, db):
        form = ApartmentOnboardingForm()
        assert form.fields["address"].label == "Adresse der Wohnung"
        assert form.fields["access_method"].label == "Zugangsart"

    def test_all_access_methods(self, db):
        for method in ["key_handover", "lockbox", "smart_lock"]:
            data = {
                "address": "Test 1, 1010 Wien",
                "access_method": method,
            }
            form = ApartmentOnboardingForm(data=data)
            assert form.is_valid(), f"Access method {method} should be valid"


class TestPlanSelectionForm:
    def test_valid_basis_plan(self):
        form = PlanSelectionForm(data={"plan": "basis"})
        assert form.is_valid()

    def test_valid_standard_plan(self):
        form = PlanSelectionForm(data={"plan": "standard"})
        assert form.is_valid()

    def test_valid_premium_plan(self):
        form = PlanSelectionForm(data={"plan": "premium"})
        assert form.is_valid()

    def test_invalid_plan(self):
        form = PlanSelectionForm(data={"plan": "extra"})
        assert not form.is_valid()

    def test_missing_plan(self):
        form = PlanSelectionForm(data={})
        assert not form.is_valid()

    def test_plan_choices(self):
        form = PlanSelectionForm()
        choices = [c[0] for c in form.fields["plan"].choices]
        assert "basis" in choices
        assert "standard" in choices
        assert "premium" in choices

    def test_plan_labels_show_prices(self):
        form = PlanSelectionForm()
        labels = dict(form.fields["plan"].choices)
        assert "89" in labels["basis"]
        assert "149" in labels["standard"]
        assert "249" in labels["premium"]
