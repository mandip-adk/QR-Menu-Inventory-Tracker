import os

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F


MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_product_image(file):
    """
    Same two-layer validation pattern as Shop.logo (Day 4): extension
    allowlist first, then a real Pillow content-sniff so a renamed
    non-image file can't slip through on extension alone.
    """
    if file.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            f"Image file too large ({file.size // (1024*1024)}MB). "
            f"Maximum allowed is {MAX_IMAGE_SIZE_BYTES // (1024*1024)}MB."
        )

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )

    try:
        from PIL import Image
        file.seek(0)
        img = Image.open(file)
        img.verify()
        detected_format = (img.format or "").upper()
    except Exception:
        raise ValidationError("This file is not a valid, readable image.")
    finally:
        file.seek(0)

    allowed_formats = {"JPEG", "PNG", "WEBP"}
    if detected_format not in allowed_formats:
        raise ValidationError(
            f"Detected image format '{detected_format}' is not allowed. "
            f"Allowed formats: JPEG, PNG, WEBP."
        )


class Product(models.Model):
    """
    # Menu/Inventory item notes:
        - Each item belongs to one category (and one shop).

    # Order rules (can the item be ordered?):
    #   stock_quantity | allow_over_order | can_order?
    ---------------|------------------|------------
        0         |      False       |    No
        0         |      True        |    Yes
        3         |      False       |    Yes
      -2         |      True        |    Yes

    # In simple words:
        - If allow_over_order = True → item can always be ordered,
        -   even if stock is 0 or negative (used for made-to-order cafes).
        - If allow_over_order = False → item can only be ordered
        -   when stock_quantity > 0 (used for inventory-managed shops).

    # Stock updates:
        - adjust_stock() safely decreases stock inside a transaction,
        -   so two people ordering at the same time don’t accidentally
        -   overwrite each other’s changes.
    """

    category    = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        related_name="products",
    )

    name            = models.CharField(max_length=150)
    description     = models.TextField(blank=True)
    price           = models.DecimalField(max_digits=10, decimal_places=2)
    image           = models.ImageField(
        upload_to="product_images/",
        blank=True,
        null=True,
        validators=[validate_product_image],
    )

    stock_quantity  = models.IntegerField(default=0)  # signed: allow_over_order can drive this negative
    allow_over_order = models.BooleanField(default=False)
    is_available    = models.BooleanField(default=True)  # owner manual toggle, independent of stock

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Product"
        verbose_name_plural = "Products"
        ordering             = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_product_name_per_category",
            ),
        ]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["category", "is_available"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def clean(self):
        errors = {}

        if self.price is not None and self.price < 0:
            errors["price"] = "Price cannot be negative."

        # DB-level validation backstop for the allow_over_order business
        # rule. Without this, the Django admin or a shell session could
        # save allow_over_order=False with stock_quantity=-5, silently
        # violating the rule that "only made-to-order products may carry
        # negative stock" — is_orderable would then incorrectly report
        # False (since -5 is not > 0), but the underlying data would
        # still be in a state that should never have been reachable.
        if not self.allow_over_order and self.stock_quantity is not None and self.stock_quantity < 0:
            errors["stock_quantity"] = (
                "Stock cannot be negative unless 'allow over-order' is enabled."
            )

        # Per-category product name uniqueness, same pattern as
        # Category's per-shop uniqueness (Day 5): case-insensitive at
        # the form/clean() layer for a friendly error message, with the
        # UniqueConstraint above as the case-sensitive DB-level backstop.
        # "Coke" and "Coke" (exact) are also caught by the DB constraint
        # alone if clean() is ever bypassed (e.g. .objects.create()
        # called directly without full_clean()).
        if self.category_id and self.name:
            qs = Product.objects.filter(category=self.category, name__iexact=self.name.strip())
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors["name"] = "A product with this name already exists in this category."

        if errors:
            raise ValidationError(errors)

    # ── Orderability (the single source of truth) ────────

    @property
    def is_orderable(self):
        """
        The ONE place that encodes the allow_over_order truth table.
        Also factors in is_available — a product manually marked
        unavailable by the owner is never orderable regardless of
        stock state, since that's an explicit "don't sell this" signal
        distinct from stock running out.
        """
        if not self.is_available:
            return False
        if self.allow_over_order:
            return True
        return self.stock_quantity > 0

    @property
    def is_low_stock(self):
        """
        Simple low-stock signal for the owner dashboard (Day 17 builds
        the actual notification UI around this). Only meaningful for
        stock-tracked products — always False for allow_over_order
        items, since their stock number isn't a hard constraint.
        """
        if self.allow_over_order:
            return False
        return 0 < self.stock_quantity <= 5

    # ── Stock mutation (race-safe) ────────────────────────

    def adjust_stock(self, delta):
        """
        Atomically adjusts stock_quantity by delta (positive to add
        stock, negative to subtract on a sale). Uses select_for_update()
        to lock this product's row for the duration of the transaction,
        so two concurrent calls (e.g. two near-simultaneous orders for
        the last item) serialize instead of both reading the same
        starting stock_quantity and each independently computing a
        result that overwrites the other's change.

        Does NOT enforce allow_over_order here — that's a higher-level
        "should this sale be allowed at all" decision belonging to the
        Order placement flow (Day 11-12), which should check
        is_orderable BEFORE calling adjust_stock. This method's only
        job is "change the number safely," not "decide if changing it
        is allowed."

        This also means adjust_stock() does NOT run the negative-stock-
        without-allow_over_order business rule validation added to
        clean() — it bypasses full_clean() entirely for speed, since
        it's called on every order placement. If that validation ran
        here, a bug in the Day 11-12 order flow that forgot to check
        is_orderable first would have its mistake silently swallowed
        (the adjustment just wouldn't apply) instead of the resulting
        bad state being visible and traceable. Enforcement belongs at
        the call site, not buried inside the low-level mutation.

        Returns the refreshed stock_quantity after the update.
        """
        with transaction.atomic():
            locked = Product.objects.select_for_update().get(pk=self.pk)
            locked.stock_quantity = F("stock_quantity") + delta
            locked.save(update_fields=["stock_quantity"])
            locked.refresh_from_db(fields=["stock_quantity"])
            self.stock_quantity = locked.stock_quantity
            return self.stock_quantity
        

        