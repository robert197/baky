"""Load all seed data by delegating to seed_demo_data.

Run via Docker:
    make seed
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load all seed data (delegates to seed_demo_data)"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False")

    def handle(self, *args, **options):
        call_command("seed_demo_data", force=options["force"], stdout=self.stdout)
