from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from baky.storage import generate_thumbnail_path, generate_upload_path, validate_photo_file


class Inspection(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Geplant"
        IN_PROGRESS = "in_progress", "Laufend"
        COMPLETED = "completed", "Abgeschlossen"
        CANCELLED = "cancelled", "Storniert"

    class OverallRating(models.TextChoices):
        OK = "ok", "OK"
        ATTENTION = "attention", "Achtung"
        URGENT = "urgent", "Dringend"

    apartment = models.ForeignKey(
        "apartments.Apartment",
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inspections",
        limit_choices_to={"role": "inspector"},
    )
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    overall_rating = models.CharField(max_length=20, choices=OverallRating.choices, blank=True)
    general_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [
            models.Index(fields=["apartment", "status"]),
            models.Index(fields=["inspector", "scheduled_at"]),
        ]

    def __str__(self) -> str:
        return f"Inspection #{self.pk} — {self.apartment.address} ({self.get_status_display()})"


class InspectionItem(models.Model):
    class Result(models.TextChoices):
        OK = "ok", "OK"
        FLAGGED = "flagged", "Auffällig"
        NA = "na", "N/A"

    class Severity(models.TextChoices):
        NONE = "none", "Keine"
        LOW = "low", "Niedrig"
        MEDIUM = "medium", "Mittel"
        HIGH = "high", "Hoch"
        URGENT = "urgent", "Dringend"

    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="items")
    checklist_label = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.OK)
    notes = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.NONE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["inspection", "result"]),
        ]

    def __str__(self) -> str:
        return f"{self.checklist_label} — {self.get_result_display()}"


class Photo(models.Model):
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="photos")
    inspection_item = models.ForeignKey(
        InspectionItem,
        on_delete=models.CASCADE,
        related_name="photos",
        null=True,
        blank=True,
    )
    file = models.ImageField(upload_to=generate_upload_path, validators=[validate_photo_file])
    thumbnail = models.ImageField(upload_to=generate_thumbnail_path, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Photo #{self.pk} — {self.caption or 'Kein Titel'}"

    def save(self, *args, **kwargs) -> None:
        import os

        from baky.storage import convert_heic_to_jpeg, create_thumbnail

        # Convert HEIC/HEIF to JPEG before saving
        if self.file and not self.pk:
            ext = os.path.splitext(self.file.name)[1].lower()
            if ext in (".heic", ".heif"):
                self.file = convert_heic_to_jpeg(self.file)

        # Auto-generate thumbnail on first save
        if self.file and not self.thumbnail:
            self.thumbnail = create_thumbnail(self.file)

        super().save(*args, **kwargs)
