from django.contrib import admin
from .models import Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "price",
        "duration_minutes",
        "is_active",
        "created_at"
    )

    list_filter = (
        "business",
        "is_active",
    )

    search_fields = (
        "name",
        "business__name",
        "description"
    )

    ordering = ("business", "name")
