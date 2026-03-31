from django.core.management.base import BaseCommand

from apps.inspections.checklist_defaults import get_default_checklist_items


class Command(BaseCommand):
    help = "Display default checklist items. Use get_default_checklist_items() in code to load them."

    def handle(self, *args, **options):
        items = get_default_checklist_items()
        categories = {}
        for item in items:
            categories.setdefault(item["category"], []).append(item)

        self.stdout.write(f"Default checklist: {len(items)} items in {len(categories)} categories\n")
        for category, cat_items in categories.items():
            self.stdout.write(f"\n  {category}:")
            for item in cat_items:
                results = ", ".join(item["allowed_results"])
                self.stdout.write(f"    [{item['order']}] {item['label']} ({results})")

        self.stdout.write(self.style.SUCCESS(f"\nLoaded {len(items)} default checklist items."))
