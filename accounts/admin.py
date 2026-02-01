from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import UserAccount

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "is_active", "created_at")
    search_fields = ("phone_number",)
