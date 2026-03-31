from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Subscription, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "phone", "is_active"]
    list_filter = ["role", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (("BAKY", {"fields": ("role", "phone", "address", "availability")}),)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["owner", "plan", "status", "billing_cycle", "started_at"]
    list_filter = ["plan", "status", "billing_cycle"]
    search_fields = ["owner__username", "owner__email"]
    raw_id_fields = ["owner"]
