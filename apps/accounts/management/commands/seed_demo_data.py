"""Populate database with realistic demo data for development and demos.

Run via Docker:
    make seed
Or directly:
    python manage.py seed_demo_data
"""

import io
from datetime import date, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image

from apps.accounts.models import OnboardingProgress, Subscription, User
from apps.apartments.models import Apartment
from apps.inspections.models import Inspection, InspectionItem, Photo
from apps.reports.models import Report

SEED_USERS = [
    {
        "email": "admin@baky.at",
        "username": "admin",
        "password": "admin1234",
        "role": User.Role.ADMIN,
        "first_name": "Admin",
        "last_name": "User",
    },
    {
        "email": "anna@example.at",
        "username": "anna",
        "password": "demo1234",
        "role": User.Role.OWNER,
        "first_name": "Anna",
        "last_name": "Müller",
        "plan": Subscription.Plan.BASIS,
    },
    {
        "email": "markus@example.at",
        "username": "markus",
        "password": "demo1234",
        "role": User.Role.OWNER,
        "first_name": "Markus",
        "last_name": "Weber",
        "plan": Subscription.Plan.PREMIUM,
    },
    {
        "email": "sophie@example.at",
        "username": "sophie",
        "password": "demo1234",
        "role": User.Role.OWNER,
        "first_name": "Sophie",
        "last_name": "Fischer",
        "plan": Subscription.Plan.STANDARD,
    },
    {
        "email": "lisa@baky.at",
        "username": "lisa",
        "password": "demo1234",
        "role": User.Role.INSPECTOR,
        "first_name": "Lisa",
        "last_name": "Berger",
    },
    {
        "email": "tom@baky.at",
        "username": "tom",
        "password": "demo1234",
        "role": User.Role.INSPECTOR,
        "first_name": "Tom",
        "last_name": "Schneider",
    },
]

SEED_APARTMENTS = [
    {
        "owner_email": "anna@example.at",
        "address": "Mariahilfer Straße 45/12, 1060 Wien",
        "street": "Mariahilfer Straße 45/12",
        "zip_code": "1060",
        "access_method": Apartment.AccessMethod.LOCKBOX,
        "access_code": "4521",
        "access_notes": "Schlüsselbox neben der Eingangstür, 2. Stock",
        "status": Apartment.Status.ACTIVE,
    },
    {
        "owner_email": "anna@example.at",
        "address": "Praterstraße 78/3, 1020 Wien",
        "street": "Praterstraße 78/3",
        "zip_code": "1020",
        "access_method": Apartment.AccessMethod.SMART_LOCK,
        "access_code": "APP-789",
        "access_notes": "Smart Lock App-Code, 3. Stock links",
        "status": Apartment.Status.ACTIVE,
    },
    {
        "owner_email": "markus@example.at",
        "address": "Kärntner Ring 15/8, 1010 Wien",
        "street": "Kärntner Ring 15/8",
        "zip_code": "1010",
        "access_method": Apartment.AccessMethod.KEY_HANDOVER,
        "access_code": "",
        "access_notes": "Schlüssel beim Portier abholen",
        "status": Apartment.Status.ACTIVE,
    },
    {
        "owner_email": "markus@example.at",
        "address": "Wiedner Hauptstraße 90/5, 1050 Wien",
        "street": "Wiedner Hauptstraße 90/5",
        "zip_code": "1050",
        "access_method": Apartment.AccessMethod.LOCKBOX,
        "access_code": "9012",
        "access_notes": "Schlüsselbox im Stiegenhaus, EG rechts",
        "status": Apartment.Status.ACTIVE,
    },
    {
        "owner_email": "markus@example.at",
        "address": "Landstraßer Hauptstraße 33/7, 1030 Wien",
        "street": "Landstraßer Hauptstraße 33/7",
        "zip_code": "1030",
        "access_method": Apartment.AccessMethod.LOCKBOX,
        "access_code": "3345",
        "access_notes": "Schlüsselbox beim Hintereingang",
        "status": Apartment.Status.PAUSED,
    },
]

# Each inspection: (apartment_index, inspector_email, status, days_offset, time_slot, rating)
# days_offset: negative = days ago, positive = days from now, 0 = today
SEED_INSPECTIONS = [
    # Completed (10)
    (0, "lisa@baky.at", "completed", -45, "morning", "ok"),
    (0, "lisa@baky.at", "completed", -30, "midday", "attention"),
    (1, "lisa@baky.at", "completed", -40, "morning", "ok"),
    (1, "tom@baky.at", "completed", -25, "afternoon", "ok"),
    (2, "lisa@baky.at", "completed", -35, "morning", "urgent"),
    (2, "tom@baky.at", "completed", -20, "midday", "ok"),
    (3, "tom@baky.at", "completed", -38, "morning", "ok"),
    (3, "lisa@baky.at", "completed", -15, "afternoon", "attention"),
    (4, "tom@baky.at", "completed", -50, "morning", "ok"),
    (0, "tom@baky.at", "completed", -10, "midday", "ok"),
    # In-progress (1)
    (2, "lisa@baky.at", "in_progress", 0, "morning", ""),
    # Scheduled (4)
    (0, "lisa@baky.at", "scheduled", 1, "morning", ""),
    (1, "lisa@baky.at", "scheduled", 2, "midday", ""),
    (3, "tom@baky.at", "scheduled", 1, "afternoon", ""),
    (2, "tom@baky.at", "scheduled", 3, "morning", ""),
]

SLOT_START_HOURS = {
    "morning": (8, 0),
    "midday": (10, 30),
    "afternoon": (13, 30),
}

SLOT_DURATIONS = {
    "morning": timedelta(hours=2, minutes=30),
    "midday": timedelta(hours=2, minutes=30),
    "afternoon": timedelta(hours=2, minutes=30),
}

# Flagging patterns per rating: (number_of_flagged_items, severities)
RATING_FLAG_PATTERNS = {
    "ok": [],
    "attention": [("low",), ("medium",)],
    "urgent": [("high",), ("urgent",), ("medium",)],
}


def _make_placeholder_jpeg(color: tuple[int, int, int] = (200, 200, 200)) -> ContentFile:
    """Generate a minimal valid JPEG image as ContentFile."""
    img = Image.new("RGB", (100, 100), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    buf.seek(0)
    return ContentFile(buf.read(), name="seed_photo.jpg")


class Command(BaseCommand):
    help = "Populate database with realistic demo data for development and demos"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stdout.write(
                self.style.WARNING("Aborted: DEBUG is False (production environment). Use --force to override.")
            )
            return

        users = self._seed_users()
        apartments = self._seed_apartments(users)
        self._seed_onboarding(users)
        inspections = self._seed_inspections(apartments, users)
        self._seed_inspection_items(inspections)
        self._seed_photos(inspections)
        self._seed_reports(inspections)

        self._print_summary()

    def _seed_users(self) -> dict[str, User]:
        """Create demo users and subscriptions. Returns {email: user} mapping."""
        users = {}
        created_count = 0

        for data in SEED_USERS:
            user, created = User.objects.update_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                    "role": data["role"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "is_staff": data["role"] == User.Role.ADMIN,
                    "is_superuser": data["role"] == User.Role.ADMIN,
                },
            )
            if created:
                user.set_password(data["password"])
                user.save(update_fields=["password"])
                created_count += 1

            users[data["email"]] = user

            # Create subscription for owners
            if "plan" in data:
                Subscription.objects.get_or_create(
                    owner=user,
                    defaults={
                        "plan": data["plan"],
                        "status": Subscription.Status.ACTIVE,
                        "started_at": date.today() - timedelta(days=60),
                        "billing_cycle": Subscription.BillingCycle.MONTHLY,
                    },
                )

        self.stdout.write(f"  Users: {created_count} created, {len(SEED_USERS) - created_count} existing")
        return users

    def _seed_apartments(self, users: dict[str, User]) -> list[Apartment]:
        """Create demo apartments. Returns list in SEED_APARTMENTS order."""
        apartments = []
        created_count = 0

        for data in SEED_APARTMENTS:
            owner = users[data["owner_email"]]
            apt, created = Apartment.objects.get_or_create(
                owner=owner,
                address=data["address"],
                defaults={
                    "street": data["street"],
                    "zip_code": data["zip_code"],
                    "city": "Wien",
                    "access_method": data["access_method"],
                    "access_code": data["access_code"],
                    "access_notes": data["access_notes"],
                    "status": data["status"],
                },
            )
            apartments.append(apt)
            if created:
                created_count += 1

        self.stdout.write(f"  Apartments: {created_count} created, {len(SEED_APARTMENTS) - created_count} existing")
        return apartments

    def _seed_onboarding(self, users: dict[str, User]) -> None:
        """Create completed onboarding progress for all owners."""
        created_count = 0
        for _email, user in users.items():
            if user.role != User.Role.OWNER:
                continue
            _, created = OnboardingProgress.objects.get_or_create(
                user=user,
                defaults={
                    "current_step": OnboardingProgress.Step.CONFIRMATION,
                    "is_complete": True,
                },
            )
            if created:
                created_count += 1

        self.stdout.write(f"  Onboarding: {created_count} created")

    def _seed_inspections(self, apartments: list[Apartment], users: dict[str, User]) -> list[Inspection]:
        """Create demo inspections. Returns list in SEED_INSPECTIONS order."""
        inspections = []
        created_count = 0

        now = timezone.now()
        today_local = timezone.localtime(now).date()

        for apt_idx, inspector_email, status, days_offset, time_slot, rating in SEED_INSPECTIONS:
            apartment = apartments[apt_idx]
            inspector = users[inspector_email]

            target_date = today_local + timedelta(days=days_offset)
            hour, minute = SLOT_START_HOURS[time_slot]
            scheduled_at = timezone.make_aware(
                timezone.datetime(target_date.year, target_date.month, target_date.day, hour, minute),
                timezone.get_current_timezone(),
            )
            scheduled_end = scheduled_at + SLOT_DURATIONS[time_slot]

            defaults = {
                "inspector": inspector,
                "status": status,
                "time_slot": time_slot,
                "scheduled_end": scheduled_end,
            }

            if status == "completed":
                defaults["overall_rating"] = rating
                defaults["started_at"] = scheduled_at + timedelta(minutes=5)
                defaults["completed_at"] = scheduled_at + timedelta(hours=1, minutes=30)
            elif status == "in_progress":
                defaults["started_at"] = scheduled_at + timedelta(minutes=5)

            if status == "scheduled" and days_offset >= 0:
                # For future inspections, use update_or_create so re-runs keep them fresh
                insp, created = Inspection.objects.update_or_create(
                    apartment=apartment,
                    inspector=inspector,
                    status="scheduled",
                    time_slot=time_slot,
                    defaults={
                        "scheduled_at": scheduled_at,
                        "scheduled_end": scheduled_end,
                    },
                )
            else:
                insp, created = Inspection.objects.get_or_create(
                    apartment=apartment,
                    scheduled_at=scheduled_at,
                    defaults=defaults,
                )

            inspections.append(insp)
            if created:
                created_count += 1

        self.stdout.write(f"  Inspections: {created_count} created, {len(SEED_INSPECTIONS) - created_count} existing")
        return inspections

    def _seed_inspection_items(self, inspections: list[Inspection]) -> None:
        """Create inspection items for completed and in-progress inspections."""
        created_count = 0

        for i, (_, _, status, _, _, rating) in enumerate(SEED_INSPECTIONS):
            if status not in ("completed", "in_progress"):
                continue

            inspection = inspections[i]
            if inspection.items.exists():
                continue

            checklist_items = inspection.apartment.checklist_template.items
            flag_pattern = RATING_FLAG_PATTERNS.get(rating, [])

            for j, cl_item in enumerate(checklist_items):
                result = InspectionItem.Result.OK
                severity = InspectionItem.Severity.NONE
                notes = ""

                if j < len(flag_pattern):
                    result = InspectionItem.Result.FLAGGED
                    severity = flag_pattern[j][0]
                    notes = f"Auffälligkeit bei: {cl_item['label']}"

                InspectionItem.objects.create(
                    inspection=inspection,
                    checklist_label=cl_item["label"],
                    category=cl_item["category"],
                    result=result,
                    severity=severity,
                    notes=notes,
                    order=cl_item["order"],
                )
                created_count += 1

        self.stdout.write(f"  Inspection items: {created_count} created")

    def _seed_photos(self, inspections: list[Inspection]) -> None:
        """Create placeholder photos for flagged items and general inspection photos."""
        created_count = 0

        for i, (_, _, status, _, _, _) in enumerate(SEED_INSPECTIONS):
            if status != "completed":
                continue

            inspection = inspections[i]
            if inspection.photos.exists():
                continue

            # Photo for each flagged item
            flagged_items = inspection.items.filter(result="flagged")
            for item in flagged_items:
                Photo.objects.create(
                    inspection=inspection,
                    inspection_item=item,
                    file=_make_placeholder_jpeg(color=(255, 200, 200)),
                    caption=f"Foto: {item.checklist_label}",
                )
                created_count += 1

            # One general overview photo per completed inspection
            Photo.objects.create(
                inspection=inspection,
                inspection_item=None,
                file=_make_placeholder_jpeg(color=(200, 220, 255)),
                caption="Gesamtübersicht",
            )
            created_count += 1

        self.stdout.write(f"  Photos: {created_count} created")

    def _seed_reports(self, inspections: list[Inspection]) -> None:
        """Create reports for all completed inspections."""
        created_count = 0

        for i, (_, _, status, _, _, _) in enumerate(SEED_INSPECTIONS):
            if status != "completed":
                continue

            inspection = inspections[i]
            apt = inspection.apartment
            rating_display = inspection.get_overall_rating_display()
            items_ok = inspection.items.filter(result="ok").count()
            items_flagged = inspection.items.filter(result="flagged").count()

            html_content = (
                f"<h1>Inspektionsbericht</h1>"
                f"<h2>{apt.address}</h2>"
                f"<p><strong>Bewertung:</strong> {rating_display}</p>"
                f"<p><strong>Datum:</strong> {inspection.completed_at:%d.%m.%Y}</p>"
                f"<p><strong>Inspektor:</strong> {inspection.inspector.get_full_name()}</p>"
                f"<hr>"
                f"<p>{items_ok} OK / {items_flagged} Auffällig</p>"
            )

            _, created = Report.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "status": Report.Status.COMPLETED,
                    "html_content": html_content,
                    "generated_at": inspection.completed_at + timedelta(hours=1),
                },
            )
            if created:
                created_count += 1

        self.stdout.write(f"  Reports: {created_count} created")

    def _print_summary(self) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed data loaded successfully!"))
        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write("  ┌─────────────────────────┬──────────┬──────────────────┐")
        self.stdout.write("  │ Email                   │ Password │ Role             │")
        self.stdout.write("  ├─────────────────────────┼──────────┼──────────────────┤")
        self.stdout.write("  │ admin@baky.at           │ admin1234│ Admin            │")
        self.stdout.write("  │ anna@example.at         │ demo1234 │ Owner (Basis)    │")
        self.stdout.write("  │ markus@example.at       │ demo1234 │ Owner (Premium)  │")
        self.stdout.write("  │ sophie@example.at       │ demo1234 │ Owner (Standard) │")
        self.stdout.write("  │ lisa@baky.at            │ demo1234 │ Inspector        │")
        self.stdout.write("  │ tom@baky.at             │ demo1234 │ Inspector        │")
        self.stdout.write("  └─────────────────────────┴──────────┴──────────────────┘")
