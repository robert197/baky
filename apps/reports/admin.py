from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Report


@admin.register(Report)
class ReportAdmin(ModelAdmin):
    list_display = ["__str__", "status", "generated_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["inspection__apartment__address"]
    raw_id_fields = ["inspection"]
    readonly_fields = ["generated_at", "created_at", "updated_at"]
    fieldsets = (
        (
            "Bericht",
            {
                "fields": ("inspection", "status", "generated_at"),
            },
        ),
        (
            "Inhalt",
            {
                "fields": ("html_content", "error_message"),
                "classes": ("collapse",),
            },
        ),
        (
            "Zeitstempel",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
