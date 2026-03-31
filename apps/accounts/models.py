from django.contrib.auth.models import AbstractUser
from django.db import models


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

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.owner.username} — {self.get_plan_display()} ({self.get_status_display()})"
