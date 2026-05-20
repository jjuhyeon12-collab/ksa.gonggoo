from django.db import models
from django.conf import settings
from django.utils import timezone


class GroupBuy(models.Model):
    class BuyType(models.TextChoices):
        BUNDLE = "bundle", "묶음 나눠사기"       # 정확한 개수 맞춰야 매칭
        MIN_ORDER = "min_order", "최소주문금액"  # 목표금액 이상이면 매칭

    class Status(models.TextChoices):
        OPEN = "open", "모집 중"
        MATCHED = "matched", "매칭 완료"
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

    buy_type = models.CharField(
        max_length=10,
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
        """매칭 조건 충족 시 상태를 matched로 변경하고 True 반환."""
        if self.status != self.Status.OPEN:
            return False

        matched = False
        if self.buy_type == self.BuyType.BUNDLE:
            matched = self.current_count == self.total_count
        elif self.buy_type == self.BuyType.MIN_ORDER:
            matched = (
                self.target_amount is not None
                and self.current_count * self.unit_price >= self.target_amount
            )

        if matched:
            self.status = self.Status.MATCHED
            self.save(update_fields=["status"])
            return True
        return False

    def is_expired(self):
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
