from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Shop(models.Model):
    """
    A single shop/restaurant/stall on Sajilo Pasal.

    One owner (User) can eventually run multiple shops (no current
    constraint preventing it), but each shop has exactly one owner.

    slug powers two things:
    - The public customer-facing menu URL: /shop/<slug>/
    - Eventually the short QR redirect target (Day 8) maps a numeric
      ID to this shop, NOT the slug — slugs stay human-readable in the
      browser address bar, while QR codes use /s/<id>/ to stay visually
      simple and easy for low-end phone cameras to scan (per the SDD's
      QR density concern).
    """

    SHOP_TYPE_CHOICES = [
        ("kirana",     "Kirana Store"),
        ("restaurant", "Restaurant"),
        ("fruit_veg",  "Fruit / Vegetable Shop"),
        ("tea_cafe",   "Tea Shop / Cafe"),
        ("other",      "Other"),
    ]

    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shops",
    )

    name        = models.CharField(max_length=150)
    slug        = models.SlugField(max_length=170, unique=True, blank=True, db_index=True)
    shop_type   = models.CharField(max_length=20, choices=SHOP_TYPE_CHOICES, default="kirana")

    logo        = models.ImageField(upload_to="shop_logos/", blank=True, null=True)
    phone       = models.CharField(max_length=20, blank=True)
    address     = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    is_active   = models.BooleanField(default=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Shop"
        verbose_name_plural = "Shops"
        ordering             = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "is_active"]),
        ]

    def __str__(self):
        return self.name

    # ── Slug generation ──────────────────────────────────

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        """
        Builds a URL-safe slug from the shop name, appending -2, -3, etc.
        on collision. Runs only on first save (slug is blank=True and
        only auto-filled once) — renaming a shop later does NOT change
        its slug, since that would break any QR codes/links already
        printed and handed out to customers.
        """
        base_slug = slugify(self.name)[:150] or "shop"
        slug = base_slug
        counter = 2

        # Exclude self.pk in case this is ever called again on an
        # existing instance (e.g. future admin action) to avoid a shop
        # colliding with its own slug.
        while Shop.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    # ── Convenience ──────────────────────────────────────

    @property
    def menu_url_path(self):
        """Relative path to the public customer-facing menu."""
        return f"/shop/{self.slug}/"

    def get_shop_type_display_nepali(self):
        """
        Nepali label for shop_type, used in bilingual UI per the SDD's
        localization strategy. Kept as a method (not a model field) so
        it's just a lookup table, not duplicated data to keep in sync.
        """
        nepali_labels = {
            "kirana":     "किराना पसल",
            "restaurant": "रेस्टुरेन्ट",
            "fruit_veg":  "फलफूल / तरकारी पसल",
            "tea_cafe":   "चिया पसल",
            "other":      "अन्य",
        }
        return nepali_labels.get(self.shop_type, "")
    
    