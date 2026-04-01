from django.contrib import admin
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

    @admin.display(description="Letzte Inspektion")
    def last_inspection_date(self, obj):
        last = obj.inspections.filter(status="completed").order_by("-completed_at").first()
        if last and last.completed_at:
            return last.completed_at.strftime("%d.%m.%Y")
        return "—"


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(ModelAdmin):
    list_display = ["name", "apartment", "updated_at"]
    search_fields = ["name", "apartment__address"]
    raw_id_fields = ["apartment"]
