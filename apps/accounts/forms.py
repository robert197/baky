from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm

User = get_user_model()


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
