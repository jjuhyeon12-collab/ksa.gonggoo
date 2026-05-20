from django.contrib import admin
from .models import GroupBuy, Participation


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    readonly_fields = ["user", "quantity", "joined_at"]


@admin.register(GroupBuy)
class GroupBuyAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "creator", "buy_type", "status", "unit_price", "deadline", "created_at"]
    list_filter = ["status", "buy_type", "category"]
    search_fields = ["title", "description", "creator__name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ParticipationInline]
    actions = ["mark_expired"]

    @admin.action(description="선택된 공동구매를 만료 처리")
    def mark_expired(self, request, queryset):
        updated = queryset.filter(status=GroupBuy.Status.OPEN).update(status=GroupBuy.Status.EXPIRED)
        self.message_user(request, f"{updated}건 만료 처리 완료.")


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ["user", "group_buy", "quantity", "joined_at"]
    search_fields = ["user__name", "group_buy__title"]
