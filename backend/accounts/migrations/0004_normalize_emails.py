"""
기존 회원 이메일을 소문자로 일괄 정규화.
이 마이그레이션 이전에 가입한 사용자 중 이메일에 대문자가 포함된 경우
로그인 불가 및 중복 가입 허용 문제가 발생하므로 반드시 실행 필요.
"""
from django.db import migrations


def lowercase_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    to_update = []
    for user in User.objects.all():
        normalized = user.email.lower()
        if user.email != normalized:
            user.email = normalized
            to_update.append(user)
    if to_update:
        User.objects.bulk_update(to_update, ["email"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_emailverification"),
    ]

    operations = [
        migrations.RunPython(lowercase_emails, migrations.RunPython.noop),
    ]
