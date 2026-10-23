"""Django admin, for looking at and fixing the family's data by hand."""

from django.contrib import admin

from leaderboard.models import Family, Member, Message, StepEntry


class MemberInline(admin.TabularInline):
    model = Member
    extra = 0
    fields = ["name", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "invite_code", "created_at"]
    search_fields = ["name", "invite_code"]
    inlines = [MemberInline]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "family", "created_at"]
    list_filter = ["family"]
    search_fields = ["name"]
    list_select_related = ["family"]


@admin.register(StepEntry)
class StepEntryAdmin(admin.ModelAdmin):
    list_display = ["member", "day", "steps", "source", "updated_at"]
    list_filter = ["member__family", "source", "day"]
    search_fields = ["member__name"]
    date_hierarchy = "day"
    list_select_related = ["member__family"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["__str__", "kind", "as_of", "discord_status", "created_at"]
    list_filter = ["family", "kind", "discord_status"]
    readonly_fields = ["created_at"]
    list_select_related = ["family"]
