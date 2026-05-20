from rest_framework import serializers
from django.conf import settings
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password", "name", "student_id"]

    def validate_email(self, value):
        domain = value.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."
            )
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "student_id", "created_at"]
        read_only_fields = ["id", "email", "created_at"]
