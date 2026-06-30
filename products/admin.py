from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display    = ["name", "category", "price", "stock_quantity", "allow_over_order", "is_available", "is_orderable_display"]
    list_filter     = ["is_available", "allow_over_order", "category__shop"]
    search_fields   = ["name", "category__name", "category__shop__name", "category__shop__owner__email"]
    ordering        = ["category", "created_at"]

    def is_orderable_display(self, obj):
        return obj.is_orderable
    is_orderable_display.short_description = "Orderable?"
    is_orderable_display.boolean = True


    