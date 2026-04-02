import uuid
from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        INSPECTOR = "inspector", "Inspector"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    availability = models.JSONField(default=dict, blank=True, help_text="Inspector schedule data")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="Soft-delete timestamp (30-day grace period)")
    privacy_consent_at = models.DateTimeField(null=True, blank=True, help_text="DSGVO privacy consent timestamp")

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def is_owner(self) -> bool:
        return self.role == self.Role.OWNER

    @property
    def is_inspector(self) -> bool:
        return self.role == self.Role.INSPECTOR


class Subscription(TimeStampedModel):
    class Plan(models.TextChoices):
        BASIS = "basis", "Basis"
        STANDARD = "standard", "Standard"
        PREMIUM = "premium", "Premium"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        PAUSED = "paused", "Pausiert"
        CANCELLED = "cancelled", "Gekündigt"

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monatlich"
        YEARLY = "yearly", "Jährlich"

    owner = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="subscription", limit_choices_to={"role": User.Role.OWNER}
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.BASIS)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateField()
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)

    PLAN_INSPECTION_LIMITS = {
        Plan.BASIS: 2,
        Plan.STANDARD: 4,
        Plan.PREMIUM: 8,
    }

    PLAN_PRICES = {
        Plan.BASIS: 89,
        Plan.STANDARD: 149,
        Plan.PREMIUM: 249,
    }

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.owner.username} — {self.get_plan_display()} ({self.get_status_display()})"

    def get_monthly_inspection_limit(self) -> int:
        """Return the maximum number of inspections per month for this plan."""
        return self.PLAN_INSPECTION_LIMITS.get(self.plan, 2)

    def get_monthly_price(self) -> int:
        """Return the monthly price in EUR for this plan."""
        return self.PLAN_PRICES.get(self.plan, 89)

    def get_next_billing_date(self) -> date | None:
        """Return the next billing date, or None if subscription is not active."""
        if self.status != self.Status.ACTIVE:
            return None
        today = date.today()
        billing_day = min(self.started_at.day, 28)
        candidate = today.replace(day=billing_day)
        if candidate <= today:
            if today.month == 12:
                candidate = candidate.replace(year=today.year + 1, month=1)
            else:
                candidate = candidate.replace(month=today.month + 1)
        return candidate

    def get_inspections_used_this_month(self) -> int:
        """Return the number of non-cancelled inspections this month across all owner apartments."""
        from apps.inspections.models import Inspection

        today = date.today()
        return Inspection.objects.filter(
            apartment__owner=self.owner,
            status__in=[Inspection.Status.SCHEDULED, Inspection.Status.IN_PROGRESS, Inspection.Status.COMPLETED],
            scheduled_at__year=today.year,
            scheduled_at__month=today.month,
        ).count()


class EmailVerificationToken(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_verification")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "verifiziert" if self.is_verified else "ausstehend"
        return f"{self.user.email} — {status}"

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    @property
    def is_expired(self) -> bool:
        if self.is_verified:
            return False
        return timezone.now() > self.created_at + timezone.timedelta(hours=48)

    def verify(self) -> bool:
        if self.is_verified or self.is_expired:
            return False
        self.verified_at = timezone.now()
        self.save(update_fields=["verified_at"])
        return True


class OnboardingProgress(TimeStampedModel):
    """Tracks a user's progress through the onboarding wizard."""

    class Step(models.IntegerChoices):
        APARTMENT = 1, "Wohnung"
        CHECKLIST = 2, "Checkliste"
        PLAN = 3, "Plan"
        CONFIRMATION = 4, "Bestätigung"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="onboarding")
    current_step = models.IntegerField(choices=Step.choices, default=Step.APARTMENT)
    apartment = models.ForeignKey(
        "apartments.Apartment", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    selected_plan = models.CharField(max_length=20, blank=True)
    is_complete = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} — Schritt {self.current_step}"


class DataExportRequest(TimeStampedModel):
    """Tracks DSGVO data export requests (Art. 15 Auskunftsrecht)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Ausstehend"
        PROCESSING = "PROCESSING", "In Bearbeitung"
        COMPLETED = "COMPLETED", "Abgeschlossen"
        FAILED = "FAILED", "Fehlgeschlagen"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="data_export_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    export_file = models.FileField(upload_to="exports/%Y/%m/", blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self) -> str:
        return f"Export {self.user.email} — {self.get_status_display()}"
