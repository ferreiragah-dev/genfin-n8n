from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher
from .models import CreditCard, CreditCardExpense, TripPlan, TripToll, UserAccount, Vehicle, VehicleExpense, VehicleFrequentDestination

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "first_name", "last_name", "email", "city", "state", "is_active", "created_at")
    search_fields = ("phone_number", "first_name", "last_name", "email", "address_line", "city", "state", "zip_code", "country")
    list_filter = ("is_active", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Conta", {"fields": ("phone_number", "email", "password")}),
        ("Perfil", {"fields": ("first_name", "last_name")}),
        ("Endereco", {"fields": ("address_line", "city", "state", "zip_code", "country")}),
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
    list_display = ("name", "brand", "model", "year", "fipe_value", "fipe_variation_percent", "fuel_km_per_liter", "fuel_price_per_liter", "user")
    search_fields = ("name", "brand", "model", "user__phone_number")
    list_filter = ("year",)


@admin.register(VehicleExpense)
class VehicleExpenseAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "expense_type", "date", "amount", "is_recurring", "user")
    search_fields = ("vehicle__name", "description", "user__phone_number")
    list_filter = ("expense_type", "is_recurring")


@admin.register(VehicleFrequentDestination)
class VehicleFrequentDestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle", "periodicity", "distance_km", "user")
    search_fields = ("name", "vehicle__name", "user__phone_number")
    list_filter = ("periodicity",)


class TripTollInline(admin.TabularInline):
    model = TripToll
    extra = 0


@admin.register(TripPlan)
class TripPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "vehicle", "date", "distance_km", "user", "created_at")
    search_fields = ("title", "vehicle__name", "user__phone_number")
    list_filter = ("date",)
    inlines = [TripTollInline]


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = ("nickname", "last4", "parent_card", "closing_day", "due_day", "best_purchase_day", "limit_amount", "miles_per_point", "user")
    search_fields = ("nickname", "last4", "user__phone_number")
    list_filter = ("closing_day", "due_day", "best_purchase_day", "parent_card")


@admin.register(CreditCardExpense)
class CreditCardExpenseAdmin(admin.ModelAdmin):
    list_display = ("card", "date", "category", "amount", "user")
    search_fields = ("card__last4", "category", "description", "user__phone_number")
    list_filter = ("category", "date")
