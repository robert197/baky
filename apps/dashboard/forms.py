from django import forms

from apps.apartments.models import Apartment

INPUT_CSS = "w-full rounded-lg border border-border px-4 py-3"

OWNER_STATUS_CHOICES = [
    (Apartment.Status.ACTIVE, "Aktiv"),
    (Apartment.Status.PAUSED, "Pausiert"),
]


class ApartmentEditForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=OWNER_STATUS_CHOICES,
        label="Status",
        widget=forms.Select(attrs={"class": INPUT_CSS}),
    )

    class Meta:
        model = Apartment
        fields = ["address", "access_method", "access_code", "access_notes", "special_instructions", "status"]
        labels = {
            "address": "Adresse",
            "access_method": "Zugangsart",
            "access_code": "Zugangscode",
            "access_notes": "Zugangshinweise",
            "special_instructions": "Besondere Anweisungen",
        }
        widgets = {
            "address": forms.TextInput(attrs={"class": INPUT_CSS}),
            "access_method": forms.Select(attrs={"class": INPUT_CSS}),
            "access_code": forms.TextInput(attrs={"class": INPUT_CSS}),
            "access_notes": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
            "special_instructions": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
        }
