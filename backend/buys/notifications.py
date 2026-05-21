"""공동구매 상태 변경 알림 (이메일 + 카카오톡).

호출 시점:
  - 추가 모집 시작(extending)
  - 매칭 완료(matched)

발송 대상:
  - 개설자(주최자) : 카카오톡 + 이메일
  - 참여자 전원     : 이메일

네트워크 응답이 느릴 수 있어 요청을 지연시키지 않도록 별도 스레드에서 처리하며,
발송 실패는 무시한다 (알림은 비핵심 기능).
"""
import threading
import os

from django.conf import settings
from django.core.mail import EmailMessage


def notify_group_buy(group_buy, kind):
    """공동구매 알림을 발송한다.

    kind: 'extending' (추가 모집 시작) 또는 'matched' (매칭 완료)
    """
    participants = list(group_buy.participations.select_related("user").all())
    if not participants:
        return

    creator = group_buy.creator
    subject = _subject(group_buy, kind)
    email_body = _email_body(group_buy, kind, len(participants))

    # ── 이메일: 개설자 + 참여자 전원 ──
    emails = [p.user.email for p in participants if p.user.email]
    if emails:
        creator_email = creator.email
        others = [e for e in emails if e != creator_email]
        threading.Thread(
            target=_send_email,
            args=(subject, email_body, creator_email, others),
            daemon=True,
        ).start()

    # ── 카카오톡: 개설자(주최자)에게만 ──
    if creator.phone_number:
        kakao_msg = _kakao_body(group_buy, kind, len(participants))
        threading.Thread(
            target=_send_kakao,
            args=(creator.phone_number, kakao_msg),
            daemon=True,
        ).start()


# 하위 호환용 별칭 (기존 호출부 보호)
def send_match_notification(group_buy):
    notify_group_buy(group_buy, "matched")


# ──────────────────────────── 메시지 빌더 ────────────────────────────

def _goal_text(group_buy):
    """유형별 목표 표시 문구."""
    if group_buy.buy_type == group_buy.BuyType.MIN_ORDER:
        return f"{(group_buy.target_amount or 0):,}원"
    return f"{group_buy.total_count}개"


def _subject(group_buy, kind):
    if kind == "extending":
        return f"[GongGoo] 목표 달성! 추가 모집 시작 - {group_buy.title}"
    return f"[GongGoo] 공동구매 매칭 완료 - {group_buy.title}"


def _email_body(group_buy, kind, participant_count):
    goal = _goal_text(group_buy)
    creator = group_buy.creator
    if kind == "extending":
        head = (
            "공동구매가 목표를 달성했어요! 🎯\n"
            "지금부터 1시간 동안 추가 모집이 진행됩니다.\n\n"
        )
        tail = "추가 모집이 끝나면 최종 매칭이 완료됩니다.\n\n"
    else:
        head = "공동구매가 매칭 완료되었습니다! 🎉\n\n"
        tail = (
            "개설자와 연락해 공동구매를 진행해 주세요.\n"
            "(이 메일의 받는사람에 개설자가 포함되어 있습니다.)\n\n"
        )
    return (
        head
        + f"  상품      : {group_buy.title}\n"
        + f"  개설자    : {creator.name} ({creator.student_id})\n"
        + f"  목표      : {goal}\n"
        + f"  참여 인원 : {participant_count}명\n\n"
        + tail
        + "— GongGoo · KSA 공동구매"
    )


def _kakao_body(group_buy, kind, participant_count):
    goal = _goal_text(group_buy)
    if kind == "extending":
        title_line = "[GongGoo] 목표 달성! 추가 모집 시작 🎯"
        tail = "1시간 동안 추가 모집이 진행됩니다."
    else:
        title_line = "[GongGoo] 공동구매 매칭 완료 🎉"
        tail = "참여자와 연락해 공동구매를 진행하세요."
    return (
        f"{title_line}\n"
        f"상품: {group_buy.title}\n"
        f"목표: {goal} · {participant_count}명 참여\n"
        f"{tail}"
    )


# ──────────────────────────── 발송 ────────────────────────────

def _send_email(subject, body, creator_email, bcc_emails):
    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[creator_email],   # 개설자 (연락 담당)
            bcc=bcc_emails,       # 나머지 참여자 (서로 이메일 비공개)
        ).send(fail_silently=True)
    except Exception:
        pass


def _send_kakao(phone, message):
    """개설자 1명에게 카카오톡(또는 SMS 대체)을 발송한다.

    설정에 따라 동작:
      - KAKAO_PF_ID + KAKAO_TEMPLATE_ID 있음 → 카카오 알림톡 발송
      - 위가 없고 API 키만 있음             → 일반 SMS(문자)로 대체 발송
      - API 키 없음                         → 서버 콘솔에 출력(개발용)
    """
    api_key = os.getenv("KAKAO_API_KEY", "")
    api_secret = os.getenv("KAKAO_API_SECRET", "")
    sender = os.getenv("KAKAO_SENDER_PHONE", "")
    pf_id = os.getenv("KAKAO_PF_ID", "")
    template_id = os.getenv("KAKAO_TEMPLATE_ID", "")

    if not (api_key and api_secret and sender):
        # 개발 환경: 콘솔 출력
        print("\n" + "=" * 50)
        print("[KakaoTalk 알림 — 개발 콘솔]")
        print(f"수신(개설자): {phone}")
        print(f"내용:\n{message}")
        print("=" * 50 + "\n")
        return

    try:
        import hmac
        import hashlib
        import uuid
        import json
        from datetime import datetime, timezone
        import requests as http

        date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        salt = str(uuid.uuid4()).replace("-", "")
        signature = hmac.new(
            api_secret.encode("utf-8"),
            (date + salt).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "Authorization": (
                f"HMAC-SHA256 apiKey={api_key}, date={date}, "
                f"salt={salt}, signature={signature}"
            ),
            "Content-Type": "application/json",
        }

        msg = {
            "to": phone.replace("-", ""),
            "from": sender.replace("-", ""),
            "text": message,   # 알림톡 실패 시 SMS 대체발송 내용으로도 사용
        }
        if pf_id and template_id:
            # 카카오 알림톡 (템플릿 변수 #{내용} 사용)
            msg["kakaoOptions"] = {
                "pfId": pf_id,
                "templateId": template_id,
                "variables": {"#{내용}": message},
                "disableSms": False,   # 알림톡 실패 시 SMS로 자동 대체
            }
        # pf_id/template_id 가 없으면 위 text 로 일반 SMS 발송

        http.post(
            "https://api.solapi.com/messages/v4/send-many",
            headers=headers,
            data=json.dumps({"messages": [msg]}),
            timeout=10,
        )
    except Exception:
        pass
