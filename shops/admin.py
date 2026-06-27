from django.contrib import admin
from .models import Shop


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display    = ["name", "owner", "shop_type", "slug", "is_active", "created_at"]
    list_filter     = ["shop_type", "is_active"]
    search_fields   = ["name", "owner__email", "slug"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    ordering        = ["-created_at"]

    