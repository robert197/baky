from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.models import TimeStampedModel
from baky.storage import generate_thumbnail_path, generate_upload_path, get_signed_url, validate_photo_file

BUSINESS_HOURS_START = 8
BUSINESS_HOURS_END = 18
MIN_INSPECTION_DURATION = timedelta(hours=2)


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
    scheduled_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Ende der geplanten Inspektion. Mindestens 2 Stunden nach Beginn.",
    )
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

    def clean(self) -> None:
        super().clean()
        errors = {}

        if self.scheduled_at:
            # Auto-set scheduled_end if not provided
            if not self.scheduled_end:
                self.scheduled_end = self.scheduled_at + MIN_INSPECTION_DURATION

            # Validate business hours (8:00 - 18:00)
            local_start = timezone.localtime(self.scheduled_at)
            local_end = timezone.localtime(self.scheduled_end)
            if local_start.hour < BUSINESS_HOURS_START or local_start.hour >= BUSINESS_HOURS_END:
                errors["scheduled_at"] = (
                    f"Inspektionen müssen innerhalb der Geschäftszeiten "
                    f"({BUSINESS_HOURS_START}:00–{BUSINESS_HOURS_END}:00) geplant werden."
                )
            if local_end.hour > BUSINESS_HOURS_END or (local_end.hour == BUSINESS_HOURS_END and local_end.minute > 0):
                errors["scheduled_end"] = f"Inspektion muss vor {BUSINESS_HOURS_END}:00 enden."

            # Validate minimum 2-hour window
            if self.scheduled_end and self.scheduled_end - self.scheduled_at < MIN_INSPECTION_DURATION:
                errors["scheduled_end"] = "Mindestdauer einer Inspektion ist 2 Stunden."

            # Validate no double-booking for same inspector
            if self.inspector_id and self.scheduled_end:
                overlapping = Inspection.objects.filter(
                    inspector=self.inspector,
                    status__in=[self.Status.SCHEDULED, self.Status.IN_PROGRESS],
                    scheduled_at__lt=self.scheduled_end,
                    scheduled_end__gt=self.scheduled_at,
                )
                if self.pk:
                    overlapping = overlapping.exclude(pk=self.pk)
                if overlapping.exists():
                    errors["scheduled_at"] = "Dieser Inspektor hat bereits eine Inspektion in diesem Zeitraum."

            # Validate subscription limits (skip only for cancelled inspections)
            if self.apartment_id and self.status != self.Status.CANCELLED:
                limit_error = self._check_subscription_limit()
                if limit_error:
                    errors["apartment"] = limit_error

        if errors:
            raise ValidationError(errors)

    def _check_subscription_limit(self) -> str | None:
        """Check if the apartment's owner has reached their monthly inspection limit."""
        from apps.accounts.models import Subscription

        try:
            subscription = self.apartment.owner.subscription
        except Subscription.DoesNotExist:
            return "Der Eigentümer hat kein aktives Abonnement."

        if subscription.status != Subscription.Status.ACTIVE:
            return "Das Abonnement des Eigentümers ist nicht aktiv."

        monthly_limit = subscription.get_monthly_inspection_limit()
        local_scheduled = timezone.localtime(self.scheduled_at)
        current_month_start = local_scheduled.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if local_scheduled.month == 12:
            next_month_start = current_month_start.replace(year=local_scheduled.year + 1, month=1)
        else:
            next_month_start = current_month_start.replace(month=local_scheduled.month + 1)

        scheduled_count = Inspection.objects.filter(
            apartment__owner=self.apartment.owner,
            status__in=[self.Status.SCHEDULED, self.Status.IN_PROGRESS, self.Status.COMPLETED],
            scheduled_at__gte=current_month_start,
            scheduled_at__lt=next_month_start,
        )
        if self.pk:
            scheduled_count = scheduled_count.exclude(pk=self.pk)
        count = scheduled_count.count()

        if count >= monthly_limit:
            return (
                f"Monatliches Inspektionslimit erreicht ({count}/{monthly_limit}). "
                f"Aktueller Plan: {subscription.get_plan_display()}."
            )
        return None


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

    def get_severity_choices(self) -> list[tuple[str, str]]:
        """Return severity choices for template iteration."""
        return self.Severity.choices


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
            self.file.seek(0)
            self.thumbnail = create_thumbnail(self.file)

        super().save(*args, **kwargs)

    def get_file_url(self, expiry: int = 86400) -> str | None:
        """Get a signed URL for the photo file (default 24h expiry)."""
        return get_signed_url(self.file, expiry=expiry)

    def get_thumbnail_url(self, expiry: int = 86400) -> str | None:
        """Get a signed URL for the thumbnail (default 24h expiry)."""
        return get_signed_url(self.thumbnail, expiry=expiry)
