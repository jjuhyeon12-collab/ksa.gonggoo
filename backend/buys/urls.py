from django.urls import path
from .views import (
    GroupBuyListCreateView,
    GroupBuyDetailView,
    similar_group_buys,
    join_group_buy,
    leave_group_buy,
    skip_extension,
    complete_group_buy,
    my_buys,
)

urlpatterns = [
    path("", GroupBuyListCreateView.as_view(), name="groupbuy-list"),
    path("mine/", my_buys, name="groupbuy-mine"),
    path("similar/", similar_group_buys, name="groupbuy-similar"),
    path("<int:pk>/", GroupBuyDetailView.as_view(), name="groupbuy-detail"),
    path("<int:pk>/join/", join_group_buy, name="groupbuy-join"),
    path("<int:pk>/leave/", leave_group_buy, name="groupbuy-leave"),
    path("<int:pk>/skip-extension/", skip_extension, name="groupbuy-skip-extension"),
    path("<int:pk>/complete/", complete_group_buy, name="groupbuy-complete"),
]
