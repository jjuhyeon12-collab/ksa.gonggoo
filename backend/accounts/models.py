import random
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("이메일은 필수입니다.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=50)
    student_id = models.CharField(max_length=10, unique=True, verbose_name="학번")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="전화번호")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "student_id"]

    class Meta:
        verbose_name = "사용자"
        verbose_name_plural = "사용자들"

    def __str__(self):
        return f"{self.name} ({self.student_id})"

    def clean(self):
        from django.core.exceptions import ValidationError
        domain = self.email.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            raise ValidationError(
                f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."
            )


class EmailVerification(models.Model):
    """회원가입 시 이메일 인증코드 임시 저장 테이블"""

    email = models.EmailField(verbose_name="이메일")
    code = models.CharField(max_length=6, verbose_name="인증코드")
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False, verbose_name="사용 여부")

    CODE_EXPIRY_MINUTES = 10  # 인증코드 유효 시간(분)

    class Meta:
        verbose_name = "이메일 인증"
        verbose_name_plural = "이메일 인증 목록"

    def __str__(self):
        return f"{self.email} – {self.code}"

    @staticmethod
    def generate_code() -> str:
        """6자리 랜덤 숫자 문자열 반환 (앞자리 0 보존)"""
        return f"{random.randint(0, 999999):06d}"

    def is_expired(self) -> bool:
        return timezone.now() > self.created_at + timedelta(minutes=self.CODE_EXPIRY_MINUTES)
