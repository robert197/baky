import csv

from django.contrib import admin
from django.http import HttpResponse
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from apps.accounts.models import User

from .forms import InspectionAdminForm
from .models import Inspection, InspectionItem, Photo


class InspectionItemInline(TabularInline):
    model = InspectionItem
    extra = 0


class PhotoInline(TabularInline):
    model = Photo
    fk_name = "inspection"
    extra = 0


@admin.register(Inspection)
class InspectionAdmin(ModelAdmin):
    form = InspectionAdminForm
    list_display = ["__str__", "apartment", "inspector", "status", "overall_rating", "scheduled_at", "scheduled_end"]
    list_filter = ["status", "overall_rating", "inspector"]
    search_fields = ["apartment__address", "inspector__username"]
    raw_id_fields = ["apartment", "inspector"]
    inlines = [InspectionItemInline, PhotoInline]
    actions = ["assign_inspector", "cancel_inspections", "export_csv"]
    date_hierarchy = "scheduled_at"
    fieldsets = (
        (
            "Terminplanung",
            {
                "fields": ("apartment", "inspector", "scheduled_at", "scheduled_end", "status"),
            },
        ),
        (
            "Ergebnis",
            {
                "fields": ("overall_rating", "general_notes", "started_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @action(description="Inspektor zuweisen")
    def assign_inspector(self, request, queryset):
        """Bulk assign the first available inspector to selected inspections."""
        inspector = User.objects.filter(role=User.Role.INSPECTOR).first()
        if inspector:
            updated = queryset.filter(status=Inspection.Status.SCHEDULED).update(inspector=inspector)
            self.message_user(request, f"{updated} Inspektion(en) an {inspector} zugewiesen.")
        else:
            self.message_user(request, "Kein Inspektor verfügbar.", level="error")

    @action(description="Inspektionen stornieren")
    def cancel_inspections(self, request, queryset):
        updated = queryset.filter(status=Inspection.Status.SCHEDULED).update(status=Inspection.Status.CANCELLED)
        self.message_user(request, f"{updated} Inspektion(en) storniert.")

    @action(description="Als CSV exportieren")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="inspections.csv"'
        response.write("\ufeff")  # UTF-8 BOM for Excel

        writer = csv.writer(response)
        writer.writerow(["ID", "Wohnung", "Inspektor", "Geplant", "Ende", "Status", "Bewertung", "Notizen"])

        for inspection in queryset.select_related("apartment", "inspector"):
            writer.writerow(
                [
                    inspection.pk,
                    inspection.apartment.address,
                    inspection.inspector.get_full_name() or inspection.inspector.username,
                    inspection.scheduled_at.strftime("%d.%m.%Y %H:%M") if inspection.scheduled_at else "",
                    inspection.scheduled_end.strftime("%d.%m.%Y %H:%M") if inspection.scheduled_end else "",
                    inspection.get_status_display(),
                    inspection.get_overall_rating_display() or "",
                    inspection.general_notes,
                ]
            )

        return response


@admin.register(InspectionItem)
class InspectionItemAdmin(ModelAdmin):
    list_display = ["checklist_label", "category", "result", "severity", "inspection"]
    list_filter = ["result", "severity"]
    search_fields = ["checklist_label", "category"]
    raw_id_fields = ["inspection"]


@admin.register(Photo)
class PhotoAdmin(ModelAdmin):
    list_display = ["__str__", "inspection", "inspection_item", "created_at"]
    raw_id_fields = ["inspection", "inspection_item"]
