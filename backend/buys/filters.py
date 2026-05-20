import django_filters
from .models import GroupBuy


class GroupBuyFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=GroupBuy.Status.choices)
    buy_type = django_filters.ChoiceFilter(choices=GroupBuy.BuyType.choices)
    min_price = django_filters.NumberFilter(field_name="unit_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="unit_price", lookup_expr="lte")
    deadline_after = django_filters.DateTimeFilter(field_name="deadline", lookup_expr="gte")

    class Meta:
        model = GroupBuy
        fields = ["status", "buy_type", "min_price", "max_price", "deadline_after"]
