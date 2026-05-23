from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, EmailVerification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "name", "student_id", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["email", "name", "student_id"]
    ordering = ["student_id"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("개인정보", {"fields": ("name", "student_id")}),
        ("권한", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "student_id", "password1", "password2"),
        }),
    )


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ["email", "code", "is_used", "created_at"]
    list_filter = ["is_used"]
    search_fields = ["email"]
    ordering = ["-created_at"]
    readonly_fields = ["email", "code", "created_at"]
