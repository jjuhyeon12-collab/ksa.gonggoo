from rest_framework import serializers
from .models import GroupBuy, Participation
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
            "participant_count", "deadline", "image",
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
            "item_url", "image",
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
    # 개설자 본인이 살 수량 (모델 필드가 아니라 개설 시 참여 정보로만 사용)
    creator_quantity = serializers.IntegerField(min_value=1, write_only=True)

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
        if buy_type == GroupBuy.BuyType.BUNDLE and not data.get("total_count"):
            raise serializers.ValidationError(
                "묶음 나눠사기는 총 수량(total_count)이 필요합니다."
            )
        if buy_type == GroupBuy.BuyType.MIN_ORDER and not data.get("target_amount"):
            raise serializers.ValidationError(
                "최소주문금액 방식은 목표 금액(target_amount)이 필요합니다."
            )
        # 묶음 나눠사기: 개설자 본인 수량이 목표 개수를 넘을 수 없음
        cq = data.get("creator_quantity")
        if (
            buy_type == GroupBuy.BuyType.BUNDLE
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
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        group_buy = self.context["group_buy"]
        request = self.context["request"]

        if group_buy.status != GroupBuy.Status.OPEN:
            raise serializers.ValidationError("모집 중인 공동구매만 참여할 수 있습니다.")
        if group_buy.is_expired():
            raise serializers.ValidationError("마감된 공동구매입니다.")
        if group_buy.creator == request.user:
            raise serializers.ValidationError("자신이 개설한 공동구매에는 참여할 수 없습니다.")
        if group_buy.participations.filter(user=request.user).exists():
            raise serializers.ValidationError("이미 참여한 공동구매입니다.")

        # 묶음 나눠사기: 초과 불가
        if group_buy.buy_type == GroupBuy.BuyType.BUNDLE:
            remaining = group_buy.total_count - group_buy.current_count
            if data["quantity"] > remaining:
                raise serializers.ValidationError(
                    f"남은 수량({remaining}개)을 초과할 수 없습니다."
                )
        return data
