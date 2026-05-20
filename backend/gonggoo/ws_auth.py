"""WebSocket용 JWT 인증 미들웨어.

프론트엔드가 ws://.../ws/buys/<id>/?token=<JWT> 형태로 토큰을 쿼리스트링에
넣어 보내면, 그 토큰으로 사용자를 인증해 scope["user"]에 넣는다.
(브라우저 WebSocket API는 커스텀 헤더를 못 보내므로 쿼리스트링을 사용)
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _get_user(token):
    from rest_framework_simplejwt.tokens import AccessToken
    from django.contrib.auth import get_user_model
    try:
        access = AccessToken(token)
        return get_user_model().objects.get(id=access["user_id"])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = query.get("token", [None])[0]
        scope["user"] = await _get_user(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)
