from django.contrib import admin

from .models import Inspection, InspectionItem, Photo


class InspectionItemInline(admin.TabularInline):
    model = InspectionItem
    extra = 0


class PhotoInline(admin.TabularInline):
    model = Photo
    fk_name = "inspection"
    extra = 0


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "apartment", "inspector", "status", "overall_rating", "scheduled_at"]
    list_filter = ["status", "overall_rating"]
    search_fields = ["apartment__address", "inspector__username"]
    raw_id_fields = ["apartment", "inspector"]
    inlines = [InspectionItemInline, PhotoInline]


@admin.register(InspectionItem)
class InspectionItemAdmin(admin.ModelAdmin):
    list_display = ["checklist_label", "category", "result", "severity", "inspection"]
    list_filter = ["result", "severity"]
    search_fields = ["checklist_label", "category"]
    raw_id_fields = ["inspection"]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["__str__", "inspection", "inspection_item", "created_at"]
    raw_id_fields = ["inspection", "inspection_item"]
