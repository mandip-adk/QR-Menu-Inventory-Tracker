from django.db import models


class Category(models.Model):
    """
    A menu category belonging to exactly one shop (e.g. "Drinks",
    "Momos", "Vegetables"). Products (Day 6) attach to a category.

    Uniqueness: a category name must be unique WITHIN a shop, but the
    same name is allowed across different shops:
        Shop A -> "Drinks"   OK
        Shop B -> "Drinks"   OK (different shop)
        Shop A -> "Drinks"   REJECTED (duplicate within same shop)
    Enforced via UniqueConstraint on (shop, name), not a unique=True
    on name alone, which would wrongly forbid the cross-shop case.

    display_order exists now so a future "manual reordering" feature
    doesn't need its own migration later, but it is NOT used for
    ordering yet — Meta.ordering still sorts by created_at. No UI or
    logic should read/write this field until that feature is built.
    """

    shop          = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name          = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)  # reserved, unused for now

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Category"
        verbose_name_plural = "Categories"
        ordering             = ["created_at"]  # creation order, NOT display_order yet
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "name"],
                name="unique_category_name_per_shop",
            ),
        ]
        indexes = [
            models.Index(fields=["shop"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"

    def clean(self):
        """
    # Category name check:
        - We make sure no two categories have the same name.
        - This avoids database errors and gives a clear message
        - if someone tries to add a duplicate.
        - The check treats names like "Drinks" and "drinks" as the same,
        - so users see a friendly error instead of a crash.
        - The database itself only blocks exact matches (case-sensitive),
        - so technically "Drinks" and "drinks" could both exist if added
        - directly in code or scripts. But through forms/views, this guard
        - ensures duplicates are caught early and explained clearly.

        """
        from django.core.exceptions import ValidationError

        if self.shop_id and self.name:
            qs = Category.objects.filter(shop=self.shop, name__iexact=self.name.strip())
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    "name": "A category with this name already exists for this shop."
                })
            

