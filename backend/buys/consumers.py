import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import GroupBuy


class GroupBuyConsumer(AsyncWebsocketConsumer):
    """
    ws://host/ws/buys/<buy_id>/
    공동구매 참여 인원을 실시간으로 클라이언트에 브로드캐스트.
    """

    async def connect(self):
        self.buy_id = self.scope["url_route"]["kwargs"]["buy_id"]
        self.group_name = f"buy_{self.buy_id}"

        # 미인증 사용자 차단
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # 연결 즉시 현재 상태 전송
        data = await self._get_current_state()
        if data:
            await self.send(text_data=json.dumps(data))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # views.py의 _broadcast_count가 group_send하는 메시지를 받아 클라이언트로 전달
    async def count_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "count_update",
            "current_count": event["current_count"],
            "participant_count": event["participant_count"],
            "status": event["status"],
        }))

    @database_sync_to_async
    def _get_current_state(self):
        try:
            gb = GroupBuy.objects.get(pk=self.buy_id)
            return {
                "type": "count_update",
                "current_count": gb.current_count,
                "participant_count": gb.participant_count,
                "status": gb.status,
            }
        except GroupBuy.DoesNotExist:
            return None
