from django.contrib import admin
from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display    = ["name", "shop", "display_order", "created_at"]
    list_filter     = ["shop"]
    search_fields   = ["name", "shop__name"]
    ordering        = ["shop", "created_at"]

    