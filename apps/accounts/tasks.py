"""Background tasks for account management (GDPR data exports)."""

import io
import json
import logging
import zipfile

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_data_export(export_request_id: int) -> dict:
    """Generate a ZIP file containing all user data for DSGVO Art. 15."""
    from apps.accounts.models import DataExportRequest

    try:
        export_req = DataExportRequest.objects.select_related("user").get(pk=export_request_id)
    except DataExportRequest.DoesNotExist:
        logger.error("DataExportRequest %s not found", export_request_id)
        return {"status": "error", "message": "Export request not found"}

    export_req.status = DataExportRequest.Status.PROCESSING
    export_req.save(update_fields=["status"])

    try:
        user = export_req.user
        data = _collect_user_data(user)

        # Create ZIP
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("daten_export.json", json.dumps(data, indent=2, ensure_ascii=False, default=str))

        buffer.seek(0)
        filename = f"baky_export_{user.pk}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip"
        export_req.export_file.save(filename, ContentFile(buffer.read()), save=False)
        export_req.status = DataExportRequest.Status.COMPLETED
        export_req.completed_at = timezone.now()
        export_req.save(update_fields=["status", "completed_at", "export_file"])

        logger.info("Data export completed for user %s", user.email)
        return {"status": "success", "user_id": user.pk}

    except Exception:
        logger.exception("Data export failed for request %s", export_request_id)
        export_req.status = DataExportRequest.Status.FAILED
        export_req.save(update_fields=["status"])
        return {"status": "error", "message": "Data export generation failed"}


def _mask_value(value: str) -> str:
    """Mask sensitive values, showing only last 2 characters."""
    if not value:
        return ""
    if len(value) <= 2:
        return "**"
    return "*" * (len(value) - 2) + value[-2:]


def _collect_user_data(user) -> dict:
    """Collect all user data into a dictionary for export."""
    from apps.apartments.models import Apartment
    from apps.inspections.models import Inspection

    data = {
        "benutzer": {
            "vorname": user.first_name,
            "nachname": user.last_name,
            "email": user.email,
            "telefon": user.phone,
            "adresse": user.address,
            "rolle": user.role,
            "registriert_am": user.date_joined,
            "datenschutz_zustimmung": user.privacy_consent_at,
        },
        "wohnungen": [],
    }

    # Subscription
    try:
        sub = user.subscription
        data["abonnement"] = {
            "plan": sub.get_plan_display(),
            "status": sub.get_status_display(),
            "gestartet_am": sub.started_at,
            "abrechnungszyklus": sub.get_billing_cycle_display(),
        }
    except Exception:
        data["abonnement"] = None

    # Apartments and their inspections
    for apt in Apartment.objects.filter(owner=user):
        apt_data = {
            "adresse": apt.address,
            "zugangsart": apt.get_access_method_display(),
            "zugangscode": _mask_value(apt.access_code),
            "zugangshinweise": _mask_value(apt.access_notes),
            "besondere_hinweise": apt.special_instructions,
            "status": apt.get_status_display(),
            "inspektionen": [],
        }

        for inspection in Inspection.objects.filter(apartment=apt).select_related("inspector"):
            insp_data = {
                "datum": inspection.scheduled_at,
                "status": inspection.get_status_display(),
                "bewertung": inspection.get_overall_rating_display() or "—",
                "anmerkungen": inspection.general_notes,
                "inspektor": str(inspection.inspector) if inspection.inspector else "—",
                "eintraege": [],
                "fotos_anzahl": inspection.photos.count(),
            }

            for item in inspection.items.all():
                insp_data["eintraege"].append(
                    {
                        "kategorie": item.category,
                        "bezeichnung": item.checklist_label,
                        "ergebnis": item.get_result_display(),
                        "anmerkungen": item.notes,
                    }
                )

            apt_data["inspektionen"].append(insp_data)

        data["wohnungen"].append(apt_data)

    return data
