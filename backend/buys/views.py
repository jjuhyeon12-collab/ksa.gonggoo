from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import GroupBuy, Participation
from .serializers import (
    GroupBuyListSerializer,
    GroupBuyDetailSerializer,
    GroupBuyCreateSerializer,
    JoinSerializer,
)
from .filters import GroupBuyFilter
from .notifications import send_match_notification


class GroupBuyListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/buys/       - 공동구매 목록 (검색/필터/정렬)
    POST /api/buys/       - 공동구매 개설
    """
    queryset = GroupBuy.objects.select_related("creator").prefetch_related("participations")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = GroupBuyFilter

    # 검색 필드: 제목, 설명 전문 검색
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "deadline", "unit_price"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GroupBuyCreateSerializer
        return GroupBuyListSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]


class GroupBuyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/buys/<id>/  - 상세 조회
    PATCH  /api/buys/<id>/  - 수정 (개설자만)
    DELETE /api/buys/<id>/  - 삭제 (개설자만)
    """
    queryset = GroupBuy.objects.select_related("creator").prefetch_related(
        "participations__user"
    )
    serializer_class = GroupBuyDetailSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in ["PATCH", "PUT", "DELETE"]:
            if obj.creator != request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("개설자만 수정/삭제할 수 있습니다.")

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status == GroupBuy.Status.MATCHED:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("매칭 완료된 공동구매는 삭제할 수 없습니다.")
        instance.delete()


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

    participation = Participation.objects.create(
        group_buy=group_buy,
        user=request.user,
        quantity=serializer.validated_data["quantity"],
    )

    # 매칭 조건 확인
    matched = group_buy.check_and_match()
    if matched:
        send_match_notification(group_buy)

    # WebSocket으로 실시간 카운트 브로드캐스트
    _broadcast_count(group_buy)

    return Response(
        {
            "detail": "참여 완료" + (" (매칭 완료!)" if matched else ""),
            "current_count": group_buy.current_count,
            "matched": matched,
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

    if group_buy.status == GroupBuy.Status.MATCHED:
        return Response(
            {"detail": "매칭 완료된 공동구매는 취소할 수 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    deleted, _ = Participation.objects.filter(group_buy=group_buy, user=request.user).delete()
    if not deleted:
        return Response({"detail": "참여 내역이 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    _broadcast_count(group_buy)
    return Response({"detail": "참여 취소 완료", "current_count": group_buy.current_count})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def my_buys(request):
    """GET /api/buys/mine/ - 내가 개설하거나 참여한 공동구매 목록"""
    created = GroupBuy.objects.filter(creator=request.user)
    joined = GroupBuy.objects.filter(participations__user=request.user).exclude(creator=request.user)

    return Response({
        "created": GroupBuyListSerializer(created, many=True, context={"request": request}).data,
        "joined": GroupBuyListSerializer(joined, many=True, context={"request": request}).data,
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
