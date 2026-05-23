from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView
from .views import RegisterView, MeView, PasswordChangeView, SendVerificationCodeView

urlpatterns = [
    path("email-verify/", SendVerificationCodeView.as_view(), name="email-verify"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("me/password/", PasswordChangeView.as_view(), name="me-password"),
]
