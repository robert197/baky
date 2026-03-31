from django.contrib import admin

from .models import Apartment, ChecklistTemplate


class ChecklistTemplateInline(admin.StackedInline):
    model = ChecklistTemplate
    extra = 0


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ["address", "owner", "status", "access_method", "created_at"]
    list_filter = ["status", "access_method"]
    search_fields = ["address", "owner__username", "owner__email"]
    raw_id_fields = ["owner"]
    inlines = [ChecklistTemplateInline]


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "apartment", "updated_at"]
    search_fields = ["name", "apartment__address"]
    raw_id_fields = ["apartment"]
