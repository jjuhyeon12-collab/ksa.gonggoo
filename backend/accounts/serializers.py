from rest_framework import serializers
from django.conf import settings
from .models import User, EmailVerification


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    verification_code = serializers.CharField(write_only=True, max_length=6, min_length=6)

    class Meta:
        model = User
        fields = ["email", "password", "name", "student_id", "phone_number", "verification_code"]

    def validate_email(self, value):
        domain = value.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."
            )
        return value

    def validate(self, data):
        email = data.get("email")
        code = data.pop("verification_code")  # DB에는 저장하지 않으므로 제거

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

        # create()에서 사용할 수 있도록 임시 보관
        self._verification = verification
        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        # 사용 완료 처리 (재사용 방지)
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
        domain = value.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."
            )
        # 다른 사람이 쓰는 이메일인지 확인
        qs = User.objects.filter(email=value).exclude(pk=self.instance.pk)
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
