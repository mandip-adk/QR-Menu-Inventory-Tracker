from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, EmailVerificationOTP, DailyOTPAttemptLimit


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin panel for the Sajilo Pasal User model.
    """

    ordering        = ["-date_joined"]
    list_display    = ["email", "full_name", "is_verified", "is_active", "is_staff", "date_joined"]
    list_filter     = ["is_verified", "is_active", "is_staff"]
    search_fields   = ["email", "first_name", "last_name"]
    readonly_fields = ["date_joined", "last_login"]

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

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "password1", "password2", "is_active", "is_verified"),
        }),
    )


@admin.register(EmailVerificationOTP)
class EmailVerificationOTPAdmin(admin.ModelAdmin):
    """
    Read-mostly admin view for debugging OTP issues during development.

    Notably absent: the raw OTP code. It's never stored anywhere, so
    there's nothing here to display or search by except the hash itself
    (otp_code_hash), which is intentionally not shown — an admin viewing
    this page should not be able to read out a usable code for any user,
    same principle as Django's own admin never displaying raw passwords.
    """

    list_display    = ["user", "is_used", "failed_attempts", "is_expired_display", "created_at", "expires_at"]
    list_filter     = ["is_used"]
    search_fields   = ["user__email"]
    readonly_fields = ["user", "created_at", "expires_at"]
    ordering        = ["-created_at"]

    def is_expired_display(self, obj):
        return obj.is_expired()
    is_expired_display.short_description = "Expired?"
    is_expired_display.boolean = True


@admin.register(DailyOTPAttemptLimit)
class DailyOTPAttemptLimitAdmin(admin.ModelAdmin):
    """
    Lets staff see and, if needed, reset a user's daily attempt counter.
    """

    list_display  = ["user", "attempt_date", "attempt_count"]
    search_fields = ["user__email"]
    ordering      = ["-attempt_date"]

    