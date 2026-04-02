from django import forms

from apps.accounts.models import Subscription
from apps.apartments.models import Apartment

INPUT_CSS = "w-full rounded-lg border border-border px-4 py-3"

OWNER_STATUS_CHOICES = [
    (Apartment.Status.ACTIVE, "Aktiv"),
    (Apartment.Status.PAUSED, "Pausiert"),
]

PLAN_CHOICES = [
    (Subscription.Plan.BASIS, "Basis — €89 / Monat"),
    (Subscription.Plan.STANDARD, "Standard — €149 / Monat"),
    (Subscription.Plan.PREMIUM, "Premium — €249 / Monat"),
]


class PlanChangeRequestForm(forms.Form):
    requested_plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        label="Gewünschter Plan",
        widget=forms.RadioSelect,
    )
    message = forms.CharField(
        label="Nachricht (optional)",
        required=False,
        widget=forms.Textarea(
            attrs={"class": INPUT_CSS, "rows": 3, "placeholder": "Optionale Nachricht an unser Team"}
        ),
    )


class SubscriptionActionForm(forms.Form):
    reason = forms.CharField(
        label="Grund (optional)",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3, "placeholder": "Optionaler Grund"}),
    )


class ExtraInspectionForm(forms.Form):
    apartment = forms.ModelChoiceField(
        queryset=Apartment.objects.none(),
        label="Wohnung",
        widget=forms.Select(attrs={"class": INPUT_CSS}),
    )
    preferred_date = forms.DateField(
        label="Gewünschtes Datum",
        widget=forms.DateInput(attrs={"class": INPUT_CSS, "type": "date"}),
    )
    notes = forms.CharField(
        label="Anmerkungen (optional)",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
    )

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            self.fields["apartment"].queryset = Apartment.objects.filter(owner=owner, status=Apartment.Status.ACTIVE)


class BookingApartmentForm(forms.Form):
    apartment = forms.ModelChoiceField(
        queryset=Apartment.objects.none(),
        label="Wohnung",
        widget=forms.Select(attrs={"class": INPUT_CSS}),
    )

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            self.fields["apartment"].queryset = Apartment.objects.filter(owner=owner, status=Apartment.Status.ACTIVE)


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
            "access_code": forms.PasswordInput(attrs={"class": INPUT_CSS, "autocomplete": "off"}, render_value=True),
            "access_notes": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
            "special_instructions": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 3}),
        }
