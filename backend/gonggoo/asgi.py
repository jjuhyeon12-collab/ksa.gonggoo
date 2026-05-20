import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gonggoo.settings")

# Django 앱 로딩 후에 import (앱 레지스트리 준비 필요)
django_asgi_app = get_asgi_application()

import buys.routing
from gonggoo.ws_auth import JWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(buys.routing.websocket_urlpatterns)
    ),
})
