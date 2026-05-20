from django.urls import re_path
from .consumers import GroupBuyConsumer

websocket_urlpatterns = [
    re_path(r"ws/buys/(?P<buy_id>\d+)/$", GroupBuyConsumer.as_asgi()),
]
