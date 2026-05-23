from django.urls import path
from .views import RegisterView, MeView, PasswordChangeView, SendVerificationCodeView, CustomTokenObtainPairView

urlpatterns = [
    path("email-verify/", SendVerificationCodeView.as_view(), name="email-verify"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("me/password/", PasswordChangeView.as_view(), name="me-password"),
]
