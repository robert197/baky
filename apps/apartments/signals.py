import copy

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inspections.checklist_defaults import get_default_checklist_items

from .models import Apartment, ChecklistTemplate


@receiver(post_save, sender=Apartment)
def create_checklist_template(sender, instance, created, **kwargs):
    """Auto-create a ChecklistTemplate with default items when an Apartment is created."""
    if not created:
        return

    if ChecklistTemplate.objects.filter(apartment=instance).exists():
        return

    name = f"Checkliste — {instance.address}"[:255]
    ChecklistTemplate.objects.create(
        apartment=instance,
        name=name,
        items=copy.deepcopy(get_default_checklist_items()),
    )
