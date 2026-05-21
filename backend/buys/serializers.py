from rest_framework import serializers
from .models import GroupBuy, Participation
from .link_preview import fetch_og_image
from accounts.serializers import UserSerializer


class ParticipationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Participation
        fields = ["id", "user", "quantity", "joined_at"]
        read_only_fields = ["id", "user", "joined_at"]


class GroupBuyListSerializer(serializers.ModelSerializer):
    """목록 조회용 - 가벼운 버전"""
    creator_name = serializers.CharField(source="creator.name", read_only=True)
    creator_student_id = serializers.CharField(source="creator.student_id", read_only=True)
    current_count = serializers.IntegerField(read_only=True)
    current_amount = serializers.IntegerField(read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_joined = serializers.SerializerMethodField()

    class Meta:
        model = GroupBuy
        fields = [
            "id", "title", "description", "emoji", "category",
            "buy_type", "status", "unit_price",
            "total_count", "target_amount", "current_count", "current_amount",
            "participant_count", "deadline", "image", "item_url",
            "preview_image_url",
            "creator_name", "creator_student_id", "is_joined",
            "is_expired", "created_at",
        ]

    def get_is_joined(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.participations.filter(user=request.user).exists()
        return False


class GroupBuyDetailSerializer(serializers.ModelSerializer):
    """상세 조회용 - 참여자 목록 포함"""
    creator = UserSerializer(read_only=True)
    participations = ParticipationSerializer(many=True, read_only=True)
    current_count = serializers.IntegerField(read_only=True)
    current_amount = serializers.IntegerField(read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    my_participation = serializers.SerializerMethodField()

    class Meta:
        model = GroupBuy
        fields = [
            "id", "creator", "title", "description", "emoji", "category",
            "item_url", "image", "preview_image_url",
            "buy_type", "total_count", "target_amount", "unit_price",
            "current_count", "current_amount", "participant_count",
            "status", "deadline", "is_expired", "participations",
            "my_participation", "created_at", "updated_at",
        ]

    def get_my_participation(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            p = obj.participations.filter(user=request.user).first()
            return ParticipationSerializer(p).data if p else None
        return None


class GroupBuyCreateSerializer(serializers.ModelSerializer):
    # 개설자 본인 참여분
    # - 묶음: 개수(개)
    # - 배송비 모으기: 기여 금액(원) — unit_price 는 서버에서 1로 고정
    creator_quantity = serializers.IntegerField(min_value=1, write_only=True)
    # 배송비 모으기에서는 unit_price 를 프런트에서 보내지 않아도 됨 (서버에서 1로 설정)
    unit_price = serializers.IntegerField(min_value=1, required=False, default=1)

    class Meta:
        model = GroupBuy
        fields = [
            "id", "title", "description", "emoji", "category",
            "item_url", "image",
            "buy_type", "total_count", "target_amount",
            "unit_price", "deadline", "creator_quantity",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        buy_type = data.get("buy_type")
        if buy_type == GroupBuy.BuyType.BUNDLE:
            if not data.get("total_count"):
                raise serializers.ValidationError(
                    "묶음 나눠사기는 총 수량(total_count)이 필요합니다."
                )
            if not data.get("unit_price"):
                raise serializers.ValidationError(
                    "묶음 나눠사기는 개당 가격(unit_price)이 필요합니다."
                )
        if buy_type == GroupBuy.BuyType.GROUP_DISCOUNT:
            if not data.get("total_count"):
                raise serializers.ValidationError(
                    "단체 할인 받기는 목표 개수(total_count)가 필요합니다."
                )
            if not data.get("unit_price"):
                raise serializers.ValidationError(
                    "단체 할인 받기는 개당 가격(unit_price)이 필요합니다."
                )
        if buy_type == GroupBuy.BuyType.MIN_ORDER:
            if not data.get("target_amount"):
                raise serializers.ValidationError(
                    "최소주문금액 모으기는 목표 금액(target_amount)이 필요합니다."
                )
            # 최소주문금액 모으기: unit_price=1 고정
            # (quantity 필드가 참여자의 기여 금액(원)을 직접 담음)
            data["unit_price"] = 1
            cq = data.get("creator_quantity")
            if cq is not None and cq < 100:
                raise serializers.ValidationError(
                    "최소주문금액 모으기는 100원 이상 참여해야 합니다."
                )

        # 묶음/단체할인: 개설자 수량이 목표 개수를 넘을 수 없음
        cq = data.get("creator_quantity")
        if (
            buy_type in (GroupBuy.BuyType.BUNDLE, GroupBuy.BuyType.GROUP_DISCOUNT)
            and cq is not None
            and data.get("total_count") is not None
            and cq > data["total_count"]
        ):
            raise serializers.ValidationError(
                "본인 구매 수량이 목표 개수를 초과할 수 없습니다."
            )
        return data

    def create(self, validated_data):
        creator_quantity = validated_data.pop("creator_quantity")
        validated_data["creator"] = self.context["request"].user
        # 상품 링크가 있으면 페이지 미리보기 이미지를 추출해 저장
        item_url = validated_data.get("item_url")
        if item_url:
            validated_data["preview_image_url"] = fetch_og_image(item_url)
        group_buy = super().create(validated_data)
        # 개설자도 첫 참여자로 등록
        Participation.objects.create(
            group_buy=group_buy,
            user=group_buy.creator,
            quantity=creator_quantity,
        )
        # 개설 시점에 이미 목표를 채웠다면 바로 매칭 처리
        group_buy.check_and_match()
        return group_buy


class JoinSerializer(serializers.Serializer):
    # 묶음: 참여 개수(개) / 배송비 모으기: 기여 금액(원)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        group_buy = self.context["group_buy"]
        request = self.context["request"]

        if group_buy.status not in [GroupBuy.Status.OPEN, GroupBuy.Status.EXTENDING]:
            raise serializers.ValidationError("모집 중인 공동구매만 참여할 수 있습니다.")
        if group_buy.is_expired():
            raise serializers.ValidationError("마감된 공동구매입니다.")
        from django.utils import timezone
        if group_buy.status == GroupBuy.Status.EXTENDING and timezone.now() >= group_buy.deadline:
            raise serializers.ValidationError("추가 모집 기간이 종료되었습니다.")
        if group_buy.creator == request.user:
            raise serializers.ValidationError("자신이 개설한 공동구매에는 참여할 수 없습니다.")
        if group_buy.participations.filter(user=request.user).exists():
            raise serializers.ValidationError("이미 참여한 공동구매입니다.")

        if group_buy.buy_type == GroupBuy.BuyType.BUNDLE:
            # 묶음: 남은 개수 초과 불가
            remaining = group_buy.total_count - group_buy.current_count
            if data["quantity"] > remaining:
                raise serializers.ValidationError(
                    f"남은 수량({remaining}개)을 초과할 수 없습니다."
                )
        elif group_buy.buy_type == GroupBuy.BuyType.GROUP_DISCOUNT:
            # 단체 할인: 1개 이상, 개수 제한 없음 (목표 초과 참여 가능)
            if data["quantity"] < 1:
                raise serializers.ValidationError("1개 이상 입력해주세요.")
        elif group_buy.buy_type == GroupBuy.BuyType.MIN_ORDER:
            # 최소주문금액 모으기: quantity = 기여 금액(원), 최소 100원
            if data["quantity"] < 100:
                raise serializers.ValidationError("최소 100원 이상 입력해주세요.")

        return data
