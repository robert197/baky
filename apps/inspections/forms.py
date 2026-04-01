from django import forms

from .models import Inspection


class InspectionAdminForm(forms.ModelForm):
    class Meta:
        model = Inspection
        fields = [
            "apartment",
            "inspector",
            "scheduled_at",
            "scheduled_end",
            "status",
            "overall_rating",
            "general_notes",
            "started_at",
            "completed_at",
        ]

    def clean(self):
        cleaned_data = super().clean()
        # Populate instance fields for model-level clean() validation
        instance = self.instance
        instance.apartment = cleaned_data.get("apartment") or instance.apartment
        instance.inspector = cleaned_data.get("inspector") or instance.inspector
        instance.scheduled_at = cleaned_data.get("scheduled_at") or instance.scheduled_at
        instance.scheduled_end = cleaned_data.get("scheduled_end") or instance.scheduled_end
        instance.status = cleaned_data.get("status", instance.status)

        # Let model clean() run the scheduling validations
        instance.clean()
        return cleaned_data
