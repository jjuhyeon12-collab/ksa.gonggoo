from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.conf import settings
from .models import User, EmailVerification


def normalize_email(value: str) -> str:
    """이메일을 소문자로 통일 (핸드폰 자동 대문자 방지)"""
    return value.strip().lower()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """로그인 시 이메일 소문자 정규화 — 기기 자동완성 대소문자 문제 해결"""

    def validate(self, attrs):
        attrs[self.username_field] = normalize_email(attrs.get(self.username_field, ""))
        return super().validate(attrs)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    verification_code = serializers.CharField(write_only=True, max_length=6, min_length=6)

    class Meta:
        model = User
        fields = ["email", "password", "name", "student_id", "phone_number", "verification_code"]

    def validate_email(self, value):
        value = normalize_email(value)  # 소문자 통일

        domain = value.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."
            )

        # 대소문자 무관하게 중복 검사
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")

        return value

    def validate(self, data):
        email = data.get("email")          # validate_email에서 이미 소문자 처리됨
        code = data.pop("verification_code")

        try:
            verification = EmailVerification.objects.get(
                email=email, code=code, is_used=False
            )
        except EmailVerification.DoesNotExist:
            raise serializers.ValidationError(
                {"verification_code": "인증코드가 올바르지 않습니다."}
            )

        if verification.is_expired():
            raise serializers.ValidationError(
                {"verification_code": "인증코드가 만료되었습니다. 다시 요청해주세요."}
            )

        self._verification = verification
        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        self._verification.is_used = True
        self._verification.save(update_fields=["is_used"])
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "student_id", "phone_number", "created_at"]
        read_only_fields = ["id", "email", "created_at"]


class UserUpdateSerializer(serializers.ModelSerializer):
    """프로필 수정용 — 이메일도 변경 가능, 학교 도메인 검증 포함"""
    class Meta:
        model = User
        fields = ["email", "name", "student_id", "phone_number"]

    def validate_email(self, value):
        value = normalize_email(value)  # 소문자 통일

        domain = value.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."
            )

        qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("이미 사용 중인 이메일입니다.")

        return value

    def validate_student_id(self, value):
        qs = User.objects.filter(student_id=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("이미 사용 중인 학번입니다.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("현재 비밀번호가 올바르지 않습니다.")
        return value

    def validate(self, data):
        if data["new_password"] != data["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "새 비밀번호가 일치하지 않습니다."})
        return data

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
