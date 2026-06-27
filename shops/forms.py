from django import forms
from .models import Shop


class ShopForm(forms.ModelForm):
    """
    Used for both create and edit. slug is intentionally excluded —
    it's auto-generated once on creation and never exposed for manual
    editing (renaming a shop must not silently break a slug that's
    already printed on a QR code).
    """

    class Meta:
        model  = Shop
        fields = ["name", "shop_type", "logo", "phone", "address", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Sharma Kirana Pasal",
                "autofocus": True,
            }),
            "shop_type": forms.Select(attrs={
                "class": "form-select",
            }),
            "logo": forms.ClearableFileInput(attrs={
                "class": "form-control",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "98XXXXXXXX",
            }),
            "address": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Street, Municipality, District",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "A short description customers will see on your menu page",
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Shop name must be at least 2 characters.")
        return name
    
    