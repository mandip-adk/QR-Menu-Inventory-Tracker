from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone

from .forms import RegistrationForm, LoginForm, OTPVerificationForm
from .models import EmailVerificationOTP, DailyOTPAttemptLimit
from .utils import send_otp_email

User = get_user_model()

RESEND_COOLDOWN_SECONDS = 60


# ─────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Step 1 of 2 in onboarding:
    Creates an inactive User, sends an OTP, and redirects to verification.
    """
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.save()

            # create_for_user now returns (otp, raw_code). raw_code lives
            # only in this local variable, gets handed to the mailer, and
            # is never written to the database — only its hash is stored
            # on the otp row.
            otp, raw_code = EmailVerificationOTP.create_for_user(user)
            send_otp_email(user, raw_code)

            request.session["pending_user_id"] = user.pk
            messages.info(
                request,
                "Account created! Please check your email for the OTP verification code."
            )
            return redirect("accounts:verify_otp")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "accounts/register.html", {"form": form})


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────

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
                request.session["pending_user_id"] = user.pk

                otp, raw_code = EmailVerificationOTP.create_for_user(user)
                send_otp_email(user, raw_code)

                messages.warning(
                    request,
                    "Your account is not verified yet. "
                    "Please enter the OTP sent to your email."
                )
                return redirect("accounts:verify_otp")
            else:
                login(request, user)
                request.session.cycle_key()

                next_url = request.GET.get("next") or "dashboard:home"
                return redirect(next_url)
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "accounts/login.html", {"form": form})


# ─────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────

@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


# ─────────────────────────────────────────────
# OTP Verification
# ─────────────────────────────────────────────

def _get_active_otp(user):
    """
    Returns the single active (is_used=False) OTP for a user.
    create_for_user() guarantees at most one such row exists at a time.
    """
    return EmailVerificationOTP.objects.filter(user=user, is_used=False).first()


def _get_pending_user(request):
    """
    Resolves the user pending verification from the session-cached PK.
    """
    user_id = request.session.get("pending_user_id")
    if not user_id:
        return None
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        del request.session["pending_user_id"]
        return None


@require_http_methods(["GET", "POST"])
def verify_otp_view(request):
    """ OTP verification notes:
    - otp_code_hash is compared via otp.check_code(submitted_code), which
      hashes the submission and compares it to the stored hash using a
      constant-time comparison. The raw code is never persisted and is
      never compared with `==`.
    - Lockout cooldown is tracked in the database (failed_attempts,
      locked_until), not in the browser session.
    - After MAX_ATTEMPTS_BEFORE_RETIRE wrong guesses, the OTP retires
      itself (is_used=True) — there's no separate permanent-lock flag.
    - A daily per-user attempt ceiling caps total guesses across resends.
    - Verification runs inside transaction.atomic() with select_for_update()
      on the OTP row, so two near-simultaneous submissions can't both
      read is_used=False before either writes.
    """
    user = _get_pending_user(request)

    if user is None:
        messages.error(request, "No pending verification found. Please register or log in again.")
        return redirect("accounts:register")

    if user.is_verified:
        del request.session["pending_user_id"]
        login(request, user)
        request.session.cycle_key()
        return redirect("dashboard:home")

    daily_limit = DailyOTPAttemptLimit.get_or_reset_for_user(user)
    otp = _get_active_otp(user)
    form = OTPVerificationForm(request.POST or None)

    locked = otp.is_currently_locked() if otp else False
    wait_seconds = otp.seconds_until_unlock() if otp else 0
    daily_limit_exceeded = daily_limit.has_exceeded_limit()

    if request.method == "POST":
        if daily_limit_exceeded:
            messages.error(
                request,
                "You've reached today's verification attempt limit. Please try again tomorrow."
            )
        elif otp is None:
            messages.error(request, "No active OTP found. Please request a new one.")
        elif locked:
            messages.warning(request, f"Please wait {wait_seconds}s before trying again.")
        elif form.is_valid():
            submitted_code = form.cleaned_data["otp_code"]

            with transaction.atomic():
                locked_otp = (
                    EmailVerificationOTP.objects
                    .select_for_update()
                    .get(pk=otp.pk)
                )

                daily_limit.increment()

                if not locked_otp.is_valid():
                    messages.error(request, "This OTP is no longer valid. Please request a new one.")
                elif not locked_otp.check_code(submitted_code):
                    # check_code() does the hash + constant-time compare —
                    # never compare submitted_code to anything with `==`.
                    retired = locked_otp.record_failed_attempt()
                    if retired:
                        messages.error(
                            request,
                            "Too many failed attempts. This code is now retired — please request a new one."
                        )
                    else:
                        remaining = locked_otp.MAX_ATTEMPTS_BEFORE_RETIRE - locked_otp.failed_attempts
                        wait = EmailVerificationOTP.LOCKOUT_SCHEDULE.get(locked_otp.failed_attempts, 0)
                        messages.error(
                            request,
                            f"Incorrect OTP. {remaining} attempt(s) left before this code is retired. "
                            f"Please wait {wait}s before trying again."
                        )
                else:
                    # Success path
                    locked_otp.is_used = True
                    locked_otp.save(update_fields=["is_used"])

                    user.is_active   = True
                    user.is_verified = True
                    user.save(update_fields=["is_active", "is_verified"])

                    del request.session["pending_user_id"]

                    login(request, user)
                    request.session.cycle_key()

                    messages.success(request, "Email verified! Welcome to Sajilo Pasal.")
                    return redirect("dashboard:home")
        else:
            messages.error(request, "Please enter a valid 6-digit code.")

    return render(request, "accounts/verify_otp.html", {
        "form": form,
        "email": user.email,
        "locked": locked,
        "wait_seconds": wait_seconds,
        "daily_limit_exceeded": daily_limit_exceeded,
    })


@require_http_methods(["POST"])
def resend_otp_view(request):
    """
    Issues a fresh OTP for the pending user. Rate limiting is enforced
    via the database (most recent OTP's created_at), tied to the user
    account — not the session.
    """
    user = _get_pending_user(request)

    if user is None:
        messages.error(request, "No pending verification found.")
        return redirect("accounts:register")

    daily_limit = DailyOTPAttemptLimit.get_or_reset_for_user(user)
    if daily_limit.has_exceeded_limit():
        messages.error(
            request,
            "You've reached today's verification attempt limit. Please try again tomorrow."
        )
        return redirect("accounts:verify_otp")

    most_recent = EmailVerificationOTP.objects.filter(user=user).order_by("-created_at").first()

    if most_recent:
        elapsed = (timezone.now() - most_recent.created_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            wait = int(RESEND_COOLDOWN_SECONDS - elapsed)
            messages.warning(request, f"Please wait {wait}s before requesting another code.")
            return redirect("accounts:verify_otp")

    otp, raw_code = EmailVerificationOTP.create_for_user(user)
    send_otp_email(user, raw_code)

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect("accounts:verify_otp")

