from django.contrib import admin
from django.db.models import Max, Q
from unfold.admin import ModelAdmin, StackedInline

from .models import Apartment, ChecklistTemplate


class ChecklistTemplateInline(StackedInline):
    model = ChecklistTemplate
    extra = 0


@admin.register(Apartment)
class ApartmentAdmin(ModelAdmin):
    list_display = ["address", "owner", "status", "access_method", "last_inspection_date", "created_at"]
    list_filter = ["status", "access_method"]
    search_fields = ["address", "owner__username", "owner__email"]
    raw_id_fields = ["owner"]
    inlines = [ChecklistTemplateInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _last_inspection_date=Max(
                    "inspections__completed_at",
                    filter=Q(inspections__status="completed"),
                )
            )
        )

    @admin.display(description="Letzte Inspektion", ordering="_last_inspection_date")
    def last_inspection_date(self, obj):
        if obj._last_inspection_date:
            return obj._last_inspection_date.strftime("%d.%m.%Y")
        return "—"


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(ModelAdmin):
    list_display = ["name", "apartment", "updated_at"]
    search_fields = ["name", "apartment__address"]
    raw_id_fields = ["apartment"]
