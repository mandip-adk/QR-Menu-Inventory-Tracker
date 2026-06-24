from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
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
    Custom User model for Kirana.

    - Email is used as the login identifier (no username).
    - is_verified: set to True only after OTP confirmation (Day 3).
    - is_active: False until OTP is verified, prevents login before verification.
    """

    email       = models.EmailField(unique=True,db_index=True, verbose_name="Email Address")
    first_name  = models.CharField(max_length=100, blank=True)
    last_name   = models.CharField(max_length=100, blank=True)

    # Django internals
    is_active   = models.BooleanField(default=False)  # activated after OTP
    is_staff    = models.BooleanField(default=False)

    # Kirana-specific
    is_verified = models.BooleanField(default=False)  # OTP verified flag
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(
    auto_now=True
    )
    
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []          # email + password only for createsuperuser

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
    
