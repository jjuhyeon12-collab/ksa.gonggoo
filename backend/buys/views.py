from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q

from .models import GroupBuy, Participation
from .serializers import (
    GroupBuyListSerializer,
    GroupBuyDetailSerializer,
    GroupBuyCreateSerializer,
    JoinSerializer,
)
from .filters import GroupBuyFilter
from .notifications import notify_group_buy

# 공개 목록에 노출되는 상태
PUBLIC_STATUSES = [GroupBuy.Status.OPEN, GroupBuy.Status.EXTENDING]


class GroupBuyListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/buys/  - 공동구매 목록 (비회원도 조회 가능)
    POST /api/buys/  - 공동구매 개설 (로그인 필요)
    """
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = GroupBuyFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "deadline", "unit_price"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return (
            GroupBuy.objects
            .filter(status__in=PUBLIC_STATUSES)
            .select_related("creator")
            .prefetch_related("participations")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GroupBuyCreateSerializer
        return GroupBuyListSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        # 개설 시점에 이미 목표를 채운 경우(개설자 단독으로 달성 등) 알림 발송
        if instance.status == GroupBuy.Status.MATCHED:
            notify_group_buy(instance, "matched")
        elif instance.status == GroupBuy.Status.EXTENDING:
            notify_group_buy(instance, "extending")


class GroupBuyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/buys/<id>/  - 상세 조회 (EXTENDING 종료 자동 처리 포함)
    PATCH  /api/buys/<id>/  - 수정 (개설자만)
    DELETE /api/buys/<id>/  - 삭제 (개설자만)
    """
    queryset = GroupBuy.objects.select_related("creator").prefetch_related(
        "participations__user"
    )
    serializer_class = GroupBuyDetailSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # EXTENDING 기간이 끝났으면 상세 조회 시 자동으로 최종 매칭 처리
        if instance.status == GroupBuy.Status.EXTENDING:
            matched = instance.check_and_match()
            if matched:
                notify_group_buy(instance, "matched")
                _broadcast_count(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in ["PATCH", "PUT", "DELETE"]:
            if obj.creator != request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("개설자만 수정/삭제할 수 있습니다.")

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        if instance.status in [GroupBuy.Status.MATCHED, GroupBuy.Status.DONE]:
            raise ValidationError("매칭/완료된 공동구매는 삭제할 수 없습니다.")
        # 개설자 외 참여자가 있으면 개설 취소 불가
        if instance.participations.exclude(user=instance.creator).exists():
            raise ValidationError("이미 참여자가 있어 개설을 취소할 수 없습니다.")
        instance.delete()


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def similar_group_buys(request):
    """GET /api/buys/similar/?title=...&category=...
    같은 카테고리에서 제목이 유사한 공동구매를 반환한다.
    """
    title = request.query_params.get("title", "").strip()
    category = request.query_params.get("category", "").strip()

    if not title or not category:
        return Response({"results": []})

    # 2자 이상의 단어로 OR 검색
    words = [w for w in title.split() if len(w) >= 2]
    if not words:
        return Response({"results": []})

    q = Q()
    for word in words:
        q |= Q(title__icontains=word)

    similar = (
        GroupBuy.objects
        .filter(q, category=category, status__in=PUBLIC_STATUSES)
        .select_related("creator")
        .prefetch_related("participations")
        [:5]
    )

    return Response({
        "results": GroupBuyListSerializer(similar, many=True, context={"request": request}).data
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def join_group_buy(request, pk):
    """POST /api/buys/<id>/join/ - 공동구매 참여"""
    try:
        group_buy = GroupBuy.objects.get(pk=pk)
    except GroupBuy.DoesNotExist:
        return Response({"detail": "공동구매를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    serializer = JoinSerializer(
        data=request.data,
        context={"group_buy": group_buy, "request": request},
    )
    serializer.is_valid(raise_exception=True)

    Participation.objects.create(
        group_buy=group_buy,
        user=request.user,
        quantity=serializer.validated_data["quantity"],
    )

    prev_status = group_buy.status
    matched = group_buy.check_and_match()
    extending = (group_buy.status == GroupBuy.Status.EXTENDING)
    # OPEN → EXTENDING 으로 막 전환된 경우만(추가 모집 재참여 시엔 중복 발송 방지)
    just_extending = (prev_status == GroupBuy.Status.OPEN and extending)

    if matched:
        notify_group_buy(group_buy, "matched")
    elif just_extending:
        notify_group_buy(group_buy, "extending")

    _broadcast_count(group_buy)

    detail = "참여 완료"
    if matched:
        detail += " (매칭 완료!)"
    elif extending:
        detail += " (목표 달성! 1시간 추가 모집 중)"

    return Response(
        {
            "detail": detail,
            "current_count": group_buy.current_count,
            "matched": matched,
            "extending": extending,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def leave_group_buy(request, pk):
    """DELETE /api/buys/<id>/leave/ - 공동구매 참여 취소"""
    try:
        group_buy = GroupBuy.objects.get(pk=pk)
    except GroupBuy.DoesNotExist:
        return Response({"detail": "공동구매를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    if group_buy.status in [GroupBuy.Status.MATCHED, GroupBuy.Status.EXTENDING]:
        return Response(
            {"detail": "매칭/추가모집 중인 공동구매는 취소할 수 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    deleted, _ = Participation.objects.filter(group_buy=group_buy, user=request.user).delete()
    if not deleted:
        return Response({"detail": "참여 내역이 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    _broadcast_count(group_buy)
    return Response({"detail": "참여 취소 완료", "current_count": group_buy.current_count})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def skip_extension(request, pk):
    """POST /api/buys/<id>/skip-extension/ - 추가 모집 1시간 건너뛰기 (개설자만)"""
    try:
        group_buy = GroupBuy.objects.get(pk=pk)
    except GroupBuy.DoesNotExist:
        return Response({"detail": "공동구매를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    if group_buy.creator != request.user:
        return Response({"detail": "개설자만 건너뛸 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)

    if group_buy.status != GroupBuy.Status.EXTENDING:
        return Response(
            {"detail": "추가 모집 중인 공동구매에서만 사용할 수 있습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    group_buy.status = GroupBuy.Status.MATCHED
    group_buy.save(update_fields=["status"])
    notify_group_buy(group_buy, "matched")
    _broadcast_count(group_buy)

    return Response({"detail": "추가 모집을 건너뛰고 매칭 완료했습니다."})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def complete_group_buy(request, pk):
    """POST /api/buys/<id>/complete/ - 완료 처리 (개설자만, matched 상태에서만)"""
    try:
        group_buy = GroupBuy.objects.get(pk=pk)
    except GroupBuy.DoesNotExist:
        return Response({"detail": "공동구매를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    if group_buy.creator != request.user:
        return Response({"detail": "개설자만 완료 처리할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)

    if group_buy.status != GroupBuy.Status.MATCHED:
        return Response(
            {"detail": "매칭 완료 상태에서만 완료 처리할 수 있습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    group_buy.status = GroupBuy.Status.DONE
    group_buy.save(update_fields=["status"])

    return Response({"detail": "완료 처리되었습니다."})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def my_buys(request):
    """GET /api/buys/mine/ - 내가 관련된 공동구매를 상태별로 반환."""
    user = request.user
    my_ids = set(
        list(GroupBuy.objects.filter(creator=user).values_list("id", flat=True))
        + list(Participation.objects.filter(user=user).values_list("group_buy_id", flat=True))
    )

    ctx = {"request": request}
    qs_base = GroupBuy.objects.select_related("creator").prefetch_related("participations")

    created = qs_base.filter(creator=user, status__in=PUBLIC_STATUSES)
    joined  = qs_base.filter(
        participations__user=user, status__in=PUBLIC_STATUSES
    ).exclude(creator=user)
    matched = qs_base.filter(id__in=my_ids, status=GroupBuy.Status.MATCHED)
    done    = qs_base.filter(id__in=my_ids, status=GroupBuy.Status.DONE)

    return Response({
        "created": GroupBuyListSerializer(created, many=True, context=ctx).data,
        "joined":  GroupBuyListSerializer(joined,  many=True, context=ctx).data,
        "matched": GroupBuyListSerializer(matched, many=True, context=ctx).data,
        "done":    GroupBuyListSerializer(done,    many=True, context=ctx).data,
    })


def _broadcast_count(group_buy: GroupBuy):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"buy_{group_buy.pk}",
        {
            "type": "count.update",
            "current_count": group_buy.current_count,
            "participant_count": group_buy.participant_count,
            "status": group_buy.status,
        },
    )
