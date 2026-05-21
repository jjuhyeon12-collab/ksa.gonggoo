from django.db import models
from django.conf import settings
from django.utils import timezone


class GroupBuy(models.Model):
    class BuyType(models.TextChoices):
        BUNDLE = "bundle", "묶음 나눠사기"              # 정확한 개수 맞춰야 매칭
        MIN_ORDER = "min_order", "최소주문금액 모으기"    # 목표 금액 이상이면 매칭
        GROUP_DISCOUNT = "group_discount", "단체 할인 받기"  # 목표 개수 이상이면 매칭

    class Status(models.TextChoices):
        OPEN = "open", "모집 중"
        EXTENDING = "extending", "추가 모집 중"   # 배송비 목표 달성 후 1시간 추가 모집
        MATCHED = "matched", "매칭 완료"
        DONE = "done", "완료 처리"
        CANCELLED = "cancelled", "취소됨"
        EXPIRED = "expired", "기간 만료"

    class Category(models.TextChoices):
        FOOD = "식품", "식품"
        LIVING = "생활용품", "생활용품"
        BOOK = "도서", "도서"
        DIGITAL = "디지털", "디지털"
        TAXI = "택시", "택시"
        OVERSEAS = "해외직구", "해외직구"
        SUBSCRIPTION = "정기결제", "정기결제"
        ETC = "기타", "기타"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_buys",
        verbose_name="개설자",
    )
    title = models.CharField(max_length=100, verbose_name="제목")
    description = models.TextField(blank=True, verbose_name="상세 설명")
    emoji = models.CharField(max_length=16, default="🛍️", verbose_name="대표 이모지")
    category = models.CharField(
        max_length=12,
        choices=Category.choices,
        default=Category.ETC,
        verbose_name="종류",
    )
    item_url = models.URLField(blank=True, verbose_name="상품 링크")
    image = models.ImageField(upload_to="buys/", blank=True, null=True, verbose_name="상품 이미지")
    # 상품 링크 페이지의 Open Graph 미리보기 이미지 (개설 시 자동 추출)
    preview_image_url = models.URLField(
        max_length=500, blank=True, verbose_name="링크 미리보기 이미지"
    )

    buy_type = models.CharField(
        max_length=14,
        choices=BuyType.choices,
        default=BuyType.MIN_ORDER,
        verbose_name="구매 방식",
    )

    # 묶음 나눠사기: 총 개수 고정
    total_count = models.PositiveIntegerField(null=True, blank=True, verbose_name="총 수량")
    # 최소주문금액: 목표 금액
    target_amount = models.PositiveIntegerField(null=True, blank=True, verbose_name="목표 금액(원)")

    unit_price = models.PositiveIntegerField(verbose_name="개당 가격(원)")
    deadline = models.DateTimeField(verbose_name="모집 마감일")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="상태",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "공동구매"
        verbose_name_plural = "공동구매 목록"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def current_count(self):
        return self.participations.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    @property
    def current_amount(self):
        return self.participations.aggregate(
            total=models.Sum(
                models.ExpressionWrapper(
                    models.F("quantity") * models.F("group_buy__unit_price"),
                    output_field=models.IntegerField(),
                )
            )
        )["total"] or 0

    @property
    def participant_count(self):
        return self.participations.count()

    def check_and_match(self):
        """매칭 조건 충족 시 상태를 변경하고 최종 매칭 여부를 반환.

        반환값:
          True  – 최종 matched 상태로 전환됨 (알림 발송 필요)
          False – 변화 없거나, EXTENDING 기간 시작됨 (아직 최종 매칭 아님)
        """
        from datetime import timedelta

        # EXTENDING 기간이 끝났으면 최종 매칭 처리
        if self.status == self.Status.EXTENDING:
            if timezone.now() >= self.deadline:
                self.status = self.Status.MATCHED
                self.save(update_fields=["status"])
                return True
            return False  # 아직 추가 모집 중

        if self.status != self.Status.OPEN:
            return False

        if self.buy_type == self.BuyType.BUNDLE:
            if self.current_count == self.total_count:
                self.status = self.Status.MATCHED
                self.save(update_fields=["status"])
                return True

        elif self.buy_type == self.BuyType.GROUP_DISCOUNT:
            if (
                self.total_count is not None
                and self.current_count >= self.total_count
            ):
                # 목표 달성 → 1시간 추가 모집 시작
                self.status = self.Status.EXTENDING
                self.deadline = timezone.now() + timedelta(hours=1)
                self.save(update_fields=["status", "deadline"])
                return False  # 최종 매칭은 아직

        elif self.buy_type == self.BuyType.MIN_ORDER:
            # 목표 금액 이상 모이면 → 1시간 추가 모집 시작
            if (
                self.target_amount is not None
                and self.current_amount >= self.target_amount
            ):
                self.status = self.Status.EXTENDING
                self.deadline = timezone.now() + timedelta(hours=1)
                self.save(update_fields=["status", "deadline"])
                return False  # 최종 매칭은 아직

        return False

    def is_expired(self):
        """마감일이 지난 OPEN 상태만 만료로 간주. EXTENDING은 별도 처리."""
        return timezone.now() > self.deadline and self.status == self.Status.OPEN


class Participation(models.Model):
    group_buy = models.ForeignKey(
        GroupBuy,
        on_delete=models.CASCADE,
        related_name="participations",
        verbose_name="공동구매",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="participations",
        verbose_name="참여자",
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="수량")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "참여"
        verbose_name_plural = "참여 목록"
        unique_together = [["group_buy", "user"]]  # 중복 참여 방지

    def __str__(self):
        return f"{self.user} → {self.group_buy} ({self.quantity}개)"
