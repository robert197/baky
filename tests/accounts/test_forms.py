from apps.accounts.forms import BakyPasswordResetForm, BakySetPasswordForm, LoginForm
from tests.factories import UserFactory


class TestLoginForm:
    def test_valid_credentials(self, db):
        UserFactory(username="testuser", password="testpass123")
        form = LoginForm(data={"username": "testuser", "password": "testpass123"})
        assert form.is_valid()

    def test_invalid_credentials(self, db):
        UserFactory(username="testuser", password="testpass123")
        form = LoginForm(data={"username": "testuser", "password": "wrong"})
        assert not form.is_valid()

    def test_missing_username(self, db):
        form = LoginForm(data={"username": "", "password": "testpass123"})
        assert not form.is_valid()
        assert "username" in form.errors

    def test_missing_password(self, db):
        form = LoginForm(data={"username": "testuser", "password": ""})
        assert not form.is_valid()
        assert "password" in form.errors

    def test_login_with_email(self, db):
        UserFactory(username="testuser", email="test@example.com", password="testpass123")
        form = LoginForm(data={"username": "test@example.com", "password": "testpass123"})
        assert form.is_valid()

    def test_login_with_nonexistent_email(self, db):
        UserFactory(username="testuser", password="testpass123")
        form = LoginForm(data={"username": "nobody@example.com", "password": "testpass123"})
        assert not form.is_valid()

    def test_labels_are_german(self, db):
        form = LoginForm()
        assert form.fields["username"].label == "E-Mail-Adresse"
        assert form.fields["password"].label == "Passwort"


class TestBakyPasswordResetForm:
    def test_valid_email(self, db):
        form = BakyPasswordResetForm(data={"email": "test@example.com"})
        assert form.is_valid()

    def test_invalid_email(self, db):
        form = BakyPasswordResetForm(data={"email": "notanemail"})
        assert not form.is_valid()

    def test_empty_email(self, db):
        form = BakyPasswordResetForm(data={"email": ""})
        assert not form.is_valid()

    def test_label_is_german(self, db):
        form = BakyPasswordResetForm()
        assert form.fields["email"].label == "E-Mail-Adresse"


class TestBakySetPasswordForm:
    def test_valid_passwords(self, db):
        user = UserFactory()
        form = BakySetPasswordForm(
            user, data={"new_password1": "newsecurepass123!", "new_password2": "newsecurepass123!"}
        )
        assert form.is_valid()

    def test_mismatched_passwords(self, db):
        user = UserFactory()
        form = BakySetPasswordForm(user, data={"new_password1": "newsecurepass123!", "new_password2": "different123!"})
        assert not form.is_valid()

    def test_too_short_password(self, db):
        user = UserFactory()
        form = BakySetPasswordForm(user, data={"new_password1": "short", "new_password2": "short"})
        assert not form.is_valid()

    def test_labels_are_german(self, db):
        user = UserFactory()
        form = BakySetPasswordForm(user)
        assert form.fields["new_password1"].label == "Neues Passwort"
        assert form.fields["new_password2"].label == "Neues Passwort bestätigen"
