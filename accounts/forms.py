from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class RegistrationForm(forms.ModelForm):
    """
    Owner registration form.
    Password is validated against Django's AUTH_PASSWORD_VALIDATORS.
    OTP is sent after successful save (Day 3).
    """

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Create a strong password",
            "autocomplete": "new-password",
        }),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Re-enter your password",
            "autocomplete": "new-password",
        }),
    )

    class Meta:
        model  = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "First name",
                "autofocus": True,
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Last name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "your@email.com",
                "autocomplete": "email",
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email      = self.cleaned_data["email"]
        user.is_active  = False   # held inactive until OTP verified
        user.is_verified = False
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    """
    Simple email + password login form.
    Validation of credentials is handled in the view.
    """

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "your@email.com",
            "autofocus": True,
            "autocomplete": "email",
        }),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Your password",
            "autocomplete": "current-password",
        }),
    )

    def clean_email(self):
        return self.cleaned_data.get("email", "").lower().strip()
    
    