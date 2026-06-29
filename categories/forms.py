from django import forms
from .models import Category


class CategoryForm(forms.ModelForm):
    """
    shop is intentionally NOT a form field — it's set by the view from
    the URL (which shop we're adding a category to), never from
    user-submitted data. Letting shop be form-editable would let a
    malicious POST attach a category to a shop the user doesn't own.
    """

    class Meta:
        model  = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Drinks, Momos, Vegetables",
                "autofocus": True,
            }),
        }

    def __init__(self, *args, shop=None, **kwargs):
        """
        shop is passed in explicitly by the view (not from form data)
        and stashed on the instance before validation, so clean() on
        the model has shop_id available when checking for duplicates.
        """
        super().__init__(*args, **kwargs)
        self._shop = shop
        if shop is not None:
            self.instance.shop = shop

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters.")
        return name
    
    