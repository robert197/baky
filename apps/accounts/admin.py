from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin

from .models import Subscription, User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ["username", "email", "role", "phone", "is_active", "apartment_count"]
    list_filter = ["role", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name", "phone"]
    fieldsets = BaseUserAdmin.fieldsets + (("BAKY", {"fields": ("role", "phone", "address", "availability")}),)

    @admin.display(description="Wohnungen")
    def apartment_count(self, obj) -> int:
        if obj.role == User.Role.OWNER:
            return obj.apartments.count()
        return 0


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ["owner", "plan", "status", "billing_cycle", "started_at"]
    list_filter = ["plan", "status", "billing_cycle"]
    search_fields = ["owner__username", "owner__email"]
    raw_id_fields = ["owner"]
