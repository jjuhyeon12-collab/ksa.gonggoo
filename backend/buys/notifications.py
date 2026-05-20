import requests
from django.conf import settings


def send_match_notification(group_buy):
    """매칭 완료 시 참여자 전원에게 카카오 비즈m 알림 발송"""
    api_key = settings.KAKAO_BIZM_API_KEY
    sender_key = settings.KAKAO_SENDER_KEY
    if not api_key or not sender_key:
        return  # 키 미설정 시 무시

    participants = group_buy.participations.select_related("user").all()
    for p in participants:
        _send_kakao_message(
            api_key=api_key,
            sender_key=sender_key,
            phone=_get_phone(p.user),  # User 모델에 phone 추가 시 활용
            template_code="GROUP_BUY_MATCHED",
            variables={
                "#{상품명}": group_buy.title,
                "#{개설자}": group_buy.creator.name,
            },
        )


def _send_kakao_message(api_key, sender_key, phone, template_code, variables):
    if not phone:
        return
    try:
        requests.post(
            "https://kakaoapi.aligo.in/akv10/alimtalk/send/",
            data={
                "apikey": api_key,
                "userid": "gonggoo",
                "senderkey": sender_key,
                "tpl_code": template_code,
                "sender": "15xx-xxxx",  # 발신번호 설정 필요
                "receiver_1": phone,
                "subject_1": "공동구매 매칭 완료",
                "message_1": _build_message(variables),
                **{f"button_name_1": "확인하기", "button_url_1": ""},
            },
            timeout=5,
        )
    except requests.RequestException:
        pass  # 알림 실패는 무시 (비핵심 기능)


def _build_message(variables: dict) -> str:
    msg = "공동구매 매칭이 완료되었습니다!\n상품명: #{상품명}\n개설자: #{개설자}"
    for key, value in variables.items():
        msg = msg.replace(key, value)
    return msg


def _get_phone(user) -> str:
    return getattr(user, "phone", "") or ""
