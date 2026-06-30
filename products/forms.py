from decimal import Decimal, InvalidOperation

from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    """
    category is intentionally NOT a form field — same reasoning as
    Shop on CategoryForm (Day 5): it's set by the view from the URL
    (which category we're adding this product to), never from
    user-submitted POST data, so a crafted request can't attach a
    product to a category the submitter doesn't own.
    """

    class Meta:
        model  = Product
        fields = ["name", "description", "price", "image", "stock_quantity", "allow_over_order", "is_available"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Chicken Momo",
                "autofocus": True,
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Short description shown to customers",
            }),
            "price": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "150.00",
                "step": "0.01",
                "min": "0",
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
            }),
            "stock_quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "0",
            }),
            "allow_over_order": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
            "is_available": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

    def __init__(self, *args, category=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._category = category
        if category is not None:
            self.instance.category = category
        # stock_quantity has a model-level default=0, but ModelForm
        # doesn't automatically treat an IntegerField as optional just
        # because it has a default — without this, omitting the field
        # entirely (e.g. a made-to-order product where the owner never
        # touches stock) would fail validation with "this field is
        # required" instead of falling back to 0.
        self.fields["stock_quantity"].required = False

    def clean_stock_quantity(self):
        value = self.cleaned_data.get("stock_quantity")
        return value if value is not None else 0

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None:
            raise forms.ValidationError("Price is required.")
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Product name must be at least 2 characters.")
        return name
    
    