from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from buys.models import GroupBuy, Participation


def user(email, name, sid):
    u, created = User.objects.get_or_create(
        email=email, defaults={"name": name, "student_id": sid})
    if created:
        u.set_password("gonggoo1234")
        u.save()
    return u


u105 = user("25-105@ksa.hs.kr", "정주현", "25-105")
u112 = user("25-112@ksa.hs.kr", "김민준", "25-112")
u201 = user("25-201@ksa.hs.kr", "이서윤", "25-201")
u118 = user("25-118@ksa.hs.kr", "최창환", "25-118")

now = timezone.now()

# creator_qty: 개설자 본인이 사는 수량 / joins: (참여자, 수량) 목록
SEED = [
    dict(creator=u105, emoji="🍜", title="신라면 블랙 24입 박스", category="식품",
         description="편의점은 너무 비싸요. 24입 박스 같이 사면 개당 800원대! 쿠팡 로켓배송.",
         buy_type="bundle", total_count=24, unit_price=800, days=8,
         creator_qty=5, joins=[(u112, 8), (u201, 7)]),
    dict(creator=u112, emoji="💻", title="USB-C 허브 공동주문", category="디지털",
         description="아마존 직구. 배송비가 물건값이라 같이 시킬 분 구해요. 최소 30,000원.",
         buy_type="min_order", target_amount=30000, unit_price=10000, days=6,
         creator_qty=1, joins=[(u118, 1)]),
    dict(creator=u201, emoji="🧴", title="선크림 공동구매 (라운드랩)", category="생활용품",
         description="올리브영 기획전. 3개 이상 구매 시 15% 할인 + 무료배송.",
         buy_type="min_order", target_amount=21000, unit_price=7000, days=3,
         creator_qty=1, joins=[(u112, 1)]),
    dict(creator=u118, emoji="📚", title="파이썬 알고리즘 인터뷰 책", category="도서",
         description="서점 정가 38,000원 -> 도매가 28,000원. 5권 이상 주문 시.",
         buy_type="bundle", total_count=5, unit_price=28000, days=10,
         creator_qty=1, joins=[(u105, 1), (u201, 1)]),
    dict(creator=u112, emoji="🎵", title="유튜브 프리미엄 패밀리", category="정기결제",
         description="패밀리 요금제 6명 모집. 1인당 월 3,500원.",
         buy_type="bundle", total_count=6, unit_price=3500, days=12,
         creator_qty=1, joins=[(u105, 1), (u201, 1), (u118, 1)]),
    dict(creator=u201, emoji="🍫", title="페레로 로쉐 48개입", category="식품",
         description="명절 선물용 대용량 박스. 48개 딱 맞게 모으면 구매! 개당 500원.",
         buy_type="bundle", total_count=48, unit_price=500, days=2,
         creator_qty=16, joins=[(u112, 16), (u118, 16)]),
]

# 깨끗한 데모 상태를 위해 기존 공동구매 전부 삭제 후 재생성
GroupBuy.objects.all().delete()

for s in SEED:
    joins = s.pop("joins")
    days = s.pop("days")
    creator_qty = s.pop("creator_qty")
    gb = GroupBuy.objects.create(deadline=now + timedelta(days=days), **s)
    # 개설자도 첫 참여자로 등록
    Participation.objects.create(group_buy=gb, user=gb.creator, quantity=creator_qty)
    for u, qty in joins:
        Participation.objects.create(group_buy=gb, user=u, quantity=qty)
    gb.check_and_match()

print("시드 완료:", GroupBuy.objects.count(), "건의 공동구매")
