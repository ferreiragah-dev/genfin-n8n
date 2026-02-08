from django.contrib import admin
from .models import UserAccount

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "first_name", "last_name", "email", "is_active", "created_at")
    search_fields = ("phone_number", "first_name", "last_name", "email")
    list_filter = ("is_active", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Conta", {"fields": ("phone_number", "email", "password")}),
        ("Perfil", {"fields": ("first_name", "last_name")}),
        ("Status", {"fields": ("is_active", "created_at")}),
    )
