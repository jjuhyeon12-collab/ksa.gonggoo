from django.conf import settings
from django.core.mail import send_mail

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import EmailVerification, User
from .serializers import (
    RegisterSerializer, UserSerializer, UserUpdateSerializer,
    PasswordChangeSerializer, CustomTokenObtainPairSerializer,
    normalize_email,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """이메일 소문자 정규화 로그인 뷰"""
    serializer_class = CustomTokenObtainPairSerializer


class SendVerificationCodeView(APIView):
    """이메일로 6자리 인증코드 발송"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response({"email": "이메일을 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        # 학교 이메일 검증
        domain = email.split("@")[-1]
        if domain != settings.SCHOOL_EMAIL_DOMAIN:
            return Response(
                {"email": f"학교 이메일(@{settings.SCHOOL_EMAIL_DOMAIN})만 사용 가능합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 이미 가입된 이메일 검사 (대소문자 무관)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"email": "이미 가입된 이메일입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 기존 미사용 코드 삭제 후 새 코드 생성
        EmailVerification.objects.filter(email=email).delete()
        code = EmailVerification.generate_code()
        EmailVerification.objects.create(email=email, code=code)

        # 이메일 발송
        send_mail(
            subject="[공구] 이메일 인증 코드",
            message=(
                f"안녕하세요!\n\n"
                f"공구 회원가입 인증 코드: {code}\n\n"
                f"이 코드는 {EmailVerification.CODE_EXPIRY_MINUTES}분 동안 유효합니다.\n"
                f"본인이 요청하지 않은 경우 이 메일을 무시해주세요."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({"detail": "인증코드가 발송되었습니다."}, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "비밀번호가 변경되었습니다."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
