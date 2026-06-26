import hashlib
import hmac
import secrets

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone


class UserManager(BaseUserManager):
    """
    Custom manager: email is the unique identifier, no username field.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for Sajilo Pasal.

    - Email is used as the login identifier (no username).
    - is_verified: set to True only after OTP confirmation.
    - is_active: False until OTP is verified, prevents login before verification.
    """

    email       = models.EmailField(unique=True, verbose_name="Email Address")
    first_name  = models.CharField(max_length=100, blank=True)
    last_name   = models.CharField(max_length=100, blank=True)

    is_active   = models.BooleanField(default=False)
    is_staff    = models.BooleanField(default=False)

    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"
        ordering            = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.email

    @property
    def short_name(self):
        return self.first_name or self.email.split("@")[0]


# Validates that a raw OTP string is exactly 6 digits, used both as a
# model-level guard (in case rows are ever inserted manually/via shell)
# and reused by the form layer for consistency.
otp_format_validator = RegexValidator(
    regex=r"^\d{6}$",
    message="OTP must be exactly 6 digits.",
)


class EmailVerificationOTP(models.Model):
    """
    OTP system notes:
    - The OTP is never stored in plaintext. Only its SHA-256 hash is
      persisted in otp_code_hash. The raw 6-digit code exists only in
      memory long enough to email it to the user, then it's discarded —
      anyone with database (or backup/dump) access sees only hashes,
      the same threat model password storage already protects against.
    - SHA-256 (not a slow password hasher like bcrypt/Argon2) is the
      right tool here specifically because OTPs are short-lived (minutes)
      and rate-limited/lockout-protected — a slow hash defends against
      offline brute-forcing of a value an attacker is meant to never get
      hold of in the first place, at a cost that doesn't buy much extra
      safety for a value this short-lived. Passwords need slow hashing
      because they live forever; this code is dead in under 10 minutes.
    - Comparison uses hmac.compare_digest (constant-time), not `==`,
      so verification doesn't leak timing information about how many
      leading hash bytes matched.
    - Only one active (unused) OTP per user at a time — retired via
      create_for_user(), wrapped in transaction.atomic() so a "retire
      old + create new" pair can't be split by a concurrent resend
      request landing in between.
    - After MAX_ATTEMPTS_BEFORE_RETIRE wrong guesses, this OTP retires
      itself (is_used=True) rather than tracking a separate permanent-
      lock flag.
    """

    LOCKOUT_SCHEDULE = {
        1: 60,
        2: 60,
        3: 5 * 60,
        4: 10 * 60,
        5: 30 * 60,
        6: 60 * 60,
        7: 5 * 60 * 60,
    }
    MAX_ATTEMPTS_BEFORE_RETIRE = 8

    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otps",
    )
    # Stores SHA-256(code) as a 64-char hex digest — never the raw code.
    otp_code_hash   = models.CharField(max_length=64, db_index=True)
    expires_at      = models.DateTimeField()
    is_used         = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until    = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Email Verification OTP"
        verbose_name_plural = "Email Verification OTPs"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_used"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} ({'used' if self.is_used else 'active'})"

    # ── Hashing ──────────────────────────────────────────

    @staticmethod
    def _hash_code(raw_code):
        return hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    def check_code(self, raw_code):
        """
        Constant-time comparison of a submitted raw code against the
        stored hash. Always use this — never compare otp_code_hash to
        a freshly-hashed value with `==`.
        """
        if not raw_code or not raw_code.isdigit() or len(raw_code) != 6:
            return False
        candidate_hash = self._hash_code(raw_code)
        return hmac.compare_digest(candidate_hash, self.otp_code_hash)

    # ── Generation ───────────────────────────────────────

    @staticmethod
    def generate_code():
        """
        Cryptographically secure 6-digit numeric code, zero-padded.
        Uses secrets.randbelow() — random is a Mersenne Twister, not a
        CSPRNG, and shouldn't back an authentication credential.
        """
        return f"{secrets.randbelow(1_000_000):06d}"

    @classmethod
    def create_for_user(cls, user):
        """
        Retires any existing active OTP for this user, then issues a
        fresh one, returning the RAW code (caller emails this — it is
        never persisted anywhere, only its hash is saved on this row).

        Wrapped in transaction.atomic(): the retire-old + create-new
        pair must commit together. Without this, two near-simultaneous
        resend requests could interleave — e.g. both read "no active
        OTP to retire" before either inserts, leaving two simultaneously
        active OTPs instead of the single-active-OTP invariant we rely
        on everywhere else (lockout tracking, _get_active_otp lookups).

        Returns: (otp_instance, raw_code) — caller is responsible for
        emailing raw_code and must not store it anywhere itself.
        """
        with transaction.atomic():
            cls.objects.filter(user=user, is_used=False).update(is_used=True)

            raw_code = cls.generate_code()
            expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 10)

            otp = cls.objects.create(
                user=user,
                otp_code_hash=cls._hash_code(raw_code),
                expires_at=timezone.now() + timezone.timedelta(minutes=expiry_minutes),
            )

        return otp, raw_code

    # ── Validity (single source of truth) ────────────────

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_used and not self.is_expired()

    def is_currently_locked(self):
        return bool(self.locked_until and timezone.now() < self.locked_until)

    def seconds_until_unlock(self):
        if self.locked_until and timezone.now() < self.locked_until:
            return int((self.locked_until - timezone.now()).total_seconds())
        return 0

    # ── Lockout logic ────────────────────────────────────

    def record_failed_attempt(self):
        """
        Increments failed_attempts and applies the escalating cooldown.
        At MAX_ATTEMPTS_BEFORE_RETIRE, retires the OTP outright instead
        of setting a separate permanent-lock flag.

        Returns True if this call retired the OTP.
        """
        self.failed_attempts += 1

        if self.failed_attempts >= self.MAX_ATTEMPTS_BEFORE_RETIRE:
            self.is_used = True
            self.locked_until = None
            self.save(update_fields=["failed_attempts", "is_used", "locked_until"])
            return True

        wait_seconds = self.LOCKOUT_SCHEDULE.get(self.failed_attempts, 0)
        self.locked_until = timezone.now() + timezone.timedelta(seconds=wait_seconds)
        self.save(update_fields=["failed_attempts", "locked_until"])
        return False


class DailyOTPAttemptLimit(models.Model):
    """
    Tracks total OTP verification attempts per user per calendar day,
    independent of any single OTP's failed_attempts counter — closes
    the "resend resets my attempts" brute-force loophole.
    """

    MAX_ATTEMPTS_PER_DAY = 20

    user          = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otp_attempt_limit",
    )
    attempt_date  = models.DateField(default=timezone.localdate)
    attempt_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = "Daily OTP Attempt Limit"
        verbose_name_plural = "Daily OTP Attempt Limits"

    @classmethod
    def get_or_reset_for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        today = timezone.localdate()
        if obj.attempt_date != today:
            obj.attempt_date = today
            obj.attempt_count = 0
            obj.save(update_fields=["attempt_date", "attempt_count"])
        return obj

    def has_exceeded_limit(self):
        return self.attempt_count >= self.MAX_ATTEMPTS_PER_DAY

    def increment(self):
        self.attempt_count += 1
        self.save(update_fields=["attempt_count"])

        