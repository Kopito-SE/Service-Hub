from django.contrib import admin
from .models import Business, StaffMember

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "owner",
        "phone_number",
        "email",
        "is_active",
        "created_at"
    )

    list_filter = (
        "category",
        "is_active"
    )
    search_fields = (
        "name",
        "owner__username",
        "owner__email",
        "phone_number",
        "email"
    )

    ordering = ("-created_at",)

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):

    list_display = (
        "display_name",
        "business",
        "user",
        "is_active",
        "created_at"
    )

    list_filter = (
        "business",
        "is_active"
    )

    search_fields = (
        "display_name",
        "business__name",
        "user__username",
        "user__email"
    )

    ordering = ("business", "display_name")
