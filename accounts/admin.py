from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin panel for the Kirana User model.
    Replaces Django's default username-based admin.
    """

    ordering        = ["-date_joined"]
    list_display    = ["email", "full_name", "is_verified", "is_active", "is_staff", "date_joined"]
    list_filter     = ["is_verified", "is_active", "is_staff"]
    search_fields   = ["email", "first_name", "last_name"]
    readonly_fields = ["date_joined", "last_login"]

    # Detail view fieldsets
    fieldsets = (
        (None, {
            "fields": ("email", "password")
        }),
        (_("Personal Info"), {
            "fields": ("first_name", "last_name")
        }),
        (_("Permissions"), {
            "fields": ("is_active", "is_staff", "is_superuser", "is_verified", "groups", "user_permissions")
        }),
        (_("Important Dates"), {
            "fields": ("last_login", "date_joined")
        }),
    )

    # Create user form fieldsets
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "password1", "password2", "is_active", "is_verified"),
        }),
    )

    