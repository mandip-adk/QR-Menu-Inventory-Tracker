from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from .forms import RegistrationForm, LoginForm


# Registration

@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Step 1 of 2 in onboarding:
    Creates an inactive User and redirects to OTP verification (Day 3).
    If already authenticated, bounce to dashboard.
    """
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            # Day 3 will hook in here: send_otp_email(user)
            # For now store email in session so the OTP page knows who to verify
            request.session["pending_verification_email"] = user.email
            messages.info(
                request,
                "Account created! Please check your email for the OTP verification code."
            )
            return redirect("accounts:verify_otp")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "accounts/register.html", {"form": form})



# Login


@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Authenticates with email + password.
    Blocks unverified accounts with a clear message.
    """
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            email    = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user     = authenticate(request, username=email, password=password)

            if user is None:
                messages.error(request, "Invalid email or password.")
            elif not user.is_verified:
                # Account exists but OTP not completed
                request.session["pending_verification_email"] = user.email
                messages.warning(
                    request,
                    "Your account is not verified yet. "
                    "Please enter the OTP sent to your email."
                )
                return redirect("accounts:verify_otp")
            else:
                login(request, user)
                # Respect ?next= parameter for login-protected pages
                next_url = request.GET.get("next") or "dashboard:home"
                return redirect(next_url)
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "accounts/login.html", {"form": form})



# Logout


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(
        request,
        "You have been logged out successfully."
    )
    return redirect("accounts:login")



# OTP Placeholder (fully implemented Day 3)


def verify_otp_view(request):
    """
    Placeholder — Day 3 replaces this with the full OTP workflow.
    Prevents a NoReverseMatch error when register redirects here.
    """
    return render(request, "accounts/verify_otp_placeholder.html")

