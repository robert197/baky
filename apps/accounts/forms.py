from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password

from apps.apartments.models import Apartment

User = get_user_model()

INPUT_CSS = "w-full rounded-lg border border-border px-4 py-3"


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Benutzername",
        widget=forms.TextInput(attrs={"class": "w-full rounded-lg border border-border px-4 py-3", "autofocus": True}),
    )
    password = forms.CharField(
        label="Passwort",
        widget=forms.PasswordInput(attrs={"class": "w-full rounded-lg border border-border px-4 py-3"}),
    )


class BakyPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="E-Mail-Adresse",
        widget=forms.EmailInput(attrs={"class": "w-full rounded-lg border border-border px-4 py-3", "autofocus": True}),
    )


class BakySetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Neues Passwort",
        widget=forms.PasswordInput(attrs={"class": "w-full rounded-lg border border-border px-4 py-3"}),
    )
    new_password2 = forms.CharField(
        label="Neues Passwort bestätigen",
        widget=forms.PasswordInput(attrs={"class": "w-full rounded-lg border border-border px-4 py-3"}),
    )


class SignupForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Passwort",
        widget=forms.PasswordInput(attrs={"class": INPUT_CSS}),
        min_length=8,
    )
    password2 = forms.CharField(
        label="Passwort bestätigen",
        widget=forms.PasswordInput(attrs={"class": INPUT_CSS}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]
        labels = {
            "first_name": "Vorname",
            "last_name": "Nachname",
            "email": "E-Mail-Adresse",
            "phone": "Telefonnummer",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CSS, "autofocus": True}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CSS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CSS}),
            "phone": forms.TextInput(attrs={"class": INPUT_CSS, "placeholder": "+43 ..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Diese E-Mail-Adresse ist bereits registriert.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        pw1 = cleaned_data.get("password1")
        pw2 = cleaned_data.get("password2")
        if pw1 and pw2 and pw1 != pw2:
            self.add_error("password2", "Die Passwörter stimmen nicht überein.")
        if pw1:
            try:
                validate_password(pw1, self.instance)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.role = User.Role.OWNER
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ApartmentOnboardingForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = [
            "address",
            "street",
            "zip_code",
            "city",
            "latitude",
            "longitude",
            "access_method",
            "access_code",
            "access_notes",
            "special_instructions",
        ]
        labels = {
            "address": "Adresse der Wohnung",
            "street": "Straße und Hausnummer",
            "zip_code": "PLZ",
            "city": "Stadt",
            "access_method": "Zugangsart",
            "access_code": "Zugangscode",
            "access_notes": "Zugangshinweise",
            "special_instructions": "Besondere Hinweise",
        }
        widgets = {
            "address": forms.TextInput(
                attrs={
                    "class": INPUT_CSS,
                    "placeholder": "Musterstraße 1/5, 1010 Wien",
                    "autofocus": True,
                    "id": "id_address",
                    "autocomplete": "off",
                }
            ),
            "street": forms.HiddenInput(),
            "zip_code": forms.HiddenInput(),
            "city": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "access_method": forms.Select(attrs={"class": INPUT_CSS}),
            "access_code": forms.TextInput(attrs={"class": INPUT_CSS, "placeholder": "PIN oder Code"}),
            "access_notes": forms.Textarea(
                attrs={
                    "class": INPUT_CSS,
                    "rows": 3,
                    "placeholder": "z.B. Schlüssel beim Portier im Erdgeschoss",
                }
            ),
            "special_instructions": forms.Textarea(
                attrs={
                    "class": INPUT_CSS,
                    "rows": 3,
                    "placeholder": "z.B. Bitte Schuhe ausziehen",
                }
            ),
        }
        help_texts = {
            "access_code": "Nur bei Schlüsselbox oder Smart Lock erforderlich.",
            "access_notes": "Diese Informationen werden verschlüsselt gespeichert.",
        }


class PlanSelectionForm(forms.Form):
    plan = forms.ChoiceField(
        choices=[
            ("basis", "Basis — € 89 / Monat"),
            ("standard", "Standard — € 149 / Monat"),
            ("premium", "Premium — € 249 / Monat"),
        ],
        widget=forms.RadioSelect,
        label="Ihr Plan",
    )
