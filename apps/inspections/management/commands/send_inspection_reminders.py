"""Send day-before reminders for upcoming inspections.

Run daily via cron or Django-Q2 schedule:
    make manage CMD="send_inspection_reminders"

Finds all SCHEDULED inspections for tomorrow and queues reminder
tasks for both inspectors and apartment owners.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.inspections.models import Inspection
from baky.tasks import queue_task


class Command(BaseCommand):
    help = "Send day-before reminders for tomorrow's inspections"

    def handle(self, *args, **options):
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        inspections = Inspection.objects.filter(
            status=Inspection.Status.SCHEDULED,
            scheduled_at__date=tomorrow,
        ).select_related("inspector", "apartment", "apartment__owner")

        count = 0
        for inspection in inspections:
            queue_task(
                "apps.inspections.tasks.send_inspection_reminder",
                inspection.pk,
                task_name=f"reminder-inspector-{inspection.pk}",
            )
            queue_task(
                "apps.inspections.tasks.send_owner_reminder",
                inspection.pk,
                task_name=f"reminder-owner-{inspection.pk}",
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} Erinnerung(en) für {tomorrow} in die Warteschlange gestellt."))
