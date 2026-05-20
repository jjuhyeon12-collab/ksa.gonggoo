from django.urls import path
from .views import (
    GroupBuyListCreateView,
    GroupBuyDetailView,
    join_group_buy,
    leave_group_buy,
    my_buys,
)

urlpatterns = [
    path("", GroupBuyListCreateView.as_view(), name="groupbuy-list"),
    path("mine/", my_buys, name="groupbuy-mine"),
    path("<int:pk>/", GroupBuyDetailView.as_view(), name="groupbuy-detail"),
    path("<int:pk>/join/", join_group_buy, name="groupbuy-join"),
    path("<int:pk>/leave/", leave_group_buy, name="groupbuy-leave"),
]
