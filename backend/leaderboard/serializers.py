"""Request and response bodies. Each serializer matches a schema in openapi.yaml, field for field."""

from datetime import timedelta

from rest_framework import serializers

from leaderboard.dates import today_eastern
from leaderboard.models import Family, Member, StepEntry

MAX_DAILY_STEPS = 100_000
MAX_ENTRIES_PER_REQUEST = 366  # a year of days, enough for any import or backfill
HISTORY_DAYS = 14  # default range for GET /members/{id}/steps


class FamilySummarySerializer(serializers.ModelSerializer):
    """FamilySummary: what GET /families lists. No invite code, so the list can't be used to join."""

    class Meta:
        model = Family
        fields = ["id", "name", "start_date"]


class FamilySerializer(FamilySummarySerializer):
    """Family: one family, including its invite code."""

    class Meta(FamilySummarySerializer.Meta):
        fields = [*FamilySummarySerializer.Meta.fields, "invite_code"]
        read_only_fields = ["invite_code"]


class FamilyCreateSerializer(serializers.ModelSerializer):
    """FamilyCreate: the body of POST /families. Names are trimmed; blank names are rejected."""

    start_date = serializers.DateField(default=today_eastern)  # first day that counts; default today, Eastern

    class Meta:
        model = Family
        fields = ["name", "start_date"]


class JoinRequestSerializer(serializers.Serializer):
    """JoinRequest: the body of POST /families/join."""

    invite_code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=40)

    def validate_invite_code(self, value: str) -> str:
        # Codes are stored in uppercase, so "demo" and "DEMO" find the same family.
        return value.upper()


class MemberSerializer(serializers.ModelSerializer):
    """Member: the contract names the family by id (family_id)."""

    family_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Member
        fields = ["id", "family_id", "name"]


class StepEntryInSerializer(serializers.Serializer):
    """StepEntryIn: one day's total in a POST /steps body."""

    day = serializers.DateField()
    steps = serializers.IntegerField(
        min_value=0,
        max_value=MAX_DAILY_STEPS,
        error_messages={
            "min_value": "Steps must be 0 or more.",
            "max_value": "Steps must be 100,000 or fewer.",  # same wording as the database constraint
        },
    )


class StepsImportSerializer(serializers.Serializer):
    """StepsImport: the body of POST /steps, from manual entry or an import."""

    member_id = serializers.IntegerField()
    source = serializers.ChoiceField(choices=StepEntry.Source.choices, default=StepEntry.Source.MANUAL)
    entries = StepEntryInSerializer(many=True, allow_empty=False, max_length=MAX_ENTRIES_PER_REQUEST)

    def validate_entries(self, entries: list[dict]) -> list[dict]:
        days = [entry["day"] for entry in entries]
        today = today_eastern()
        if future := sorted({day for day in days if day > today}):
            raise serializers.ValidationError(f"These days haven't happened yet: {format_days(future)}.")
        # Which total would win is ambiguous, so the sender has to pick one.
        if repeated := sorted({day for day in days if days.count(day) > 1}):
            raise serializers.ValidationError(f"Each day can appear only once: {format_days(repeated)}.")
        return entries


class StepEntrySerializer(serializers.ModelSerializer):
    """StepEntry: a saved day's total."""

    member_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = StepEntry
        fields = ["member_id", "day", "steps", "source"]


class StepHistoryQuerySerializer(serializers.Serializer):
    """The from/to query parameters of GET /members/{id}/steps. Both optional: the default is the last 14 days."""

    def get_fields(self) -> dict:
        # "from" is a Python keyword, so it can't be written as a class attribute.
        return {"from": serializers.DateField(required=False), "to": serializers.DateField(required=False)}

    def validate(self, attrs: dict) -> dict:
        end = attrs.get("to") or today_eastern()
        start = attrs.get("from") or end - timedelta(days=HISTORY_DAYS - 1)
        if start > end:
            raise serializers.ValidationError("from must be on or before to.")
        return {"from": start, "to": end}


def format_days(days) -> str:
    return ", ".join(day.isoformat() for day in days)
