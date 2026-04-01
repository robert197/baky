from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from unfold.admin import ModelAdmin

from .models import Subscription, User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ["username", "email", "role", "phone", "is_active", "apartment_count"]
    list_filter = ["role", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name", "phone"]
    fieldsets = BaseUserAdmin.fieldsets + (("BAKY", {"fields": ("role", "phone", "address", "availability")}),)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_apartment_count=Count("apartments"))

    @admin.display(description="Wohnungen", ordering="_apartment_count")
    def apartment_count(self, obj) -> int:
        return obj._apartment_count


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ["owner", "plan", "status", "billing_cycle", "started_at"]
    list_filter = ["plan", "status", "billing_cycle"]
    search_fields = ["owner__username", "owner__email"]
    raw_id_fields = ["owner"]
