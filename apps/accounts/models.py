import uuid

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
        EXTRA = "extra", "Extra"

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
        Plan.EXTRA: 4,
    }

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.owner.username} — {self.get_plan_display()} ({self.get_status_display()})"

    def get_monthly_inspection_limit(self) -> int:
        """Return the maximum number of inspections per month for this plan."""
        return self.PLAN_INSPECTION_LIMITS.get(self.plan, 2)


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
