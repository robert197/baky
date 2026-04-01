from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

from apps.accounts.models import TimeStampedModel

VALID_RESULTS = {"ok", "flagged", "na"}
REQUIRED_ITEM_KEYS = {"category", "label", "allowed_results", "order"}


def validate_checklist_items(value: list) -> None:
    """Validate that checklist items conform to the expected JSON schema."""
    if not isinstance(value, list):
        raise ValidationError("items must be a list.")

    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"Item {i} must be a dict.")

        missing = REQUIRED_ITEM_KEYS - item.keys()
        if missing:
            raise ValidationError(f"Item {i} is missing required keys: {', '.join(sorted(missing))}")

        extra = item.keys() - REQUIRED_ITEM_KEYS
        if extra:
            raise ValidationError(f"Item {i} contains unexpected keys: {', '.join(sorted(extra))}")

        if not isinstance(item["category"], str) or not item["category"]:
            raise ValidationError(f"Item {i}: category must be a non-empty string.")

        if not isinstance(item["label"], str) or not item["label"]:
            raise ValidationError(f"Item {i}: label must be a non-empty string.")

        if not isinstance(item["allowed_results"], list) or not item["allowed_results"]:
            raise ValidationError(f"Item {i}: allowed_results must be a non-empty list.")

        invalid = set(item["allowed_results"]) - VALID_RESULTS
        if invalid:
            raise ValidationError(f"Item {i}: allowed_results contains invalid values: {', '.join(sorted(invalid))}")

        if not isinstance(item["order"], int) or isinstance(item["order"], bool) or item["order"] < 1:
            raise ValidationError(f"Item {i}: order must be a positive integer.")


class Apartment(TimeStampedModel):
    class AccessMethod(models.TextChoices):
        KEY_HANDOVER = "key_handover", "Schlüsselübergabe"
        LOCKBOX = "lockbox", "Schlüsselbox"
        SMART_LOCK = "smart_lock", "Smart Lock"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        PAUSED = "paused", "Pausiert"
        ARCHIVED = "archived", "Archiviert"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="apartments",
        limit_choices_to={"role": "owner"},
    )
    address = models.CharField(max_length=255)
    access_method = models.CharField(max_length=20, choices=AccessMethod.choices, default=AccessMethod.KEY_HANDOVER)
    access_code = EncryptedCharField(max_length=50, blank=True, help_text="Lockbox PIN or smart lock code")
    access_notes = EncryptedTextField(blank=True)
    special_instructions = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.address} ({self.get_status_display()})"


class ChecklistTemplate(TimeStampedModel):
    apartment = models.OneToOneField(Apartment, on_delete=models.CASCADE, related_name="checklist_template")
    name = models.CharField(max_length=255)
    items = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_checklist_items],
        help_text="Array of {category, label, allowed_results, order} objects",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} — {self.apartment.address}"
