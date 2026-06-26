from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_otp_email(user, raw_code):
    """
    Sends the OTP code to the user's email.

    Takes the raw code directly (not the OTP model instance) — since
    EmailVerificationOTP no longer stores the plaintext code anywhere,
    the only copy of it in existence is the one create_for_user() handed
    back to the caller. This function is that code's one and only use:
    once the email is sent, nothing in the system retains the raw value.
    """
    subject = "Your Sajilo Pasal verification code"

    context = {
        "user": user,
        "otp_code": raw_code,
        "expiry_minutes": getattr(settings, "OTP_EXPIRY_MINUTES", 10),
    }

    text_body = render_to_string("accounts/email/otp_email.txt", context)

    send_mail(
        subject=subject,
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    