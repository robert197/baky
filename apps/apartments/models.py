from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedTextField

from apps.accounts.models import TimeStampedModel


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
        help_text="Array of {category, label, type} objects",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} — {self.apartment.address}"
