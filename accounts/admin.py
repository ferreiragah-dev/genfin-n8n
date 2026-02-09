from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher
from .models import UserAccount, Vehicle, VehicleExpense

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

    def save_model(self, request, obj, form, change):
        password = obj.password or ""
        try:
            identify_hasher(password)
        except Exception:
            if password:
                obj.set_password(password)
        super().save_model(request, obj, form, change)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "model", "year", "fipe_value", "fipe_variation_percent", "user")
    search_fields = ("name", "brand", "model", "user__phone_number")
    list_filter = ("year",)


@admin.register(VehicleExpense)
class VehicleExpenseAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "expense_type", "date", "amount", "is_recurring", "user")
    search_fields = ("vehicle__name", "description", "user__phone_number")
    list_filter = ("expense_type", "is_recurring")
