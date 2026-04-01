from django.db import models

from apps.accounts.models import TimeStampedModel


class Report(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        GENERATING = "generating", "Wird erstellt"
        COMPLETED = "completed", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"

    inspection = models.OneToOneField(
        "inspections.Inspection",
        on_delete=models.CASCADE,
        related_name="report",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    html_content = models.TextField(blank=True, help_text="Rendered HTML report content")
    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True, help_text="When the report email was sent to the owner")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["inspection", "status"]),
        ]

    def __str__(self) -> str:
        return f"Report #{self.pk} — {self.inspection.apartment.address} ({self.get_status_display()})"

    @property
    def is_ready(self) -> bool:
        return self.status == self.Status.COMPLETED and bool(self.html_content)

    @property
    def overall_rating(self) -> str:
        return self.inspection.overall_rating

    @property
    def overall_rating_display(self) -> str:
        return self.inspection.get_overall_rating_display()
