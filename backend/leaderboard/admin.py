"""Django admin, for looking at and fixing the family's data by hand."""

from django import forms
from django.contrib import admin

from leaderboard.invites import CODE_LENGTH, INVITE_ALPHABET
from leaderboard.models import Family, Member, Message, StepEntry
from leaderboard.seed import DEMO_INVITE_CODE


class FamilyForm(forms.ModelForm):
    """Saves an invite code only in a form that works: joining and the X-Family-Code check compare in capitals,
    so a code saved as "abc234" could never be used. New codes are easier made with the app's "New invite code"."""

    class Meta:
        model = Family
        fields = "__all__"

    def clean_invite_code(self) -> str:
        code = self.cleaned_data["invite_code"].strip().upper()
        if code == DEMO_INVITE_CODE:
            return code
        if len(code) != CODE_LENGTH or any(c not in INVITE_ALPHABET for c in code):
            raise forms.ValidationError(
                f"An invite code is {CODE_LENGTH} characters from {INVITE_ALPHABET} (no 0, O, 1 or I)."
            )
        return code


class MemberInline(admin.TabularInline):
    model = Member
    extra = 0
    fields = ["name", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    form = FamilyForm
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
