"""Request and response bodies. Each serializer matches a schema in openapi.yaml, field for field."""

from rest_framework import serializers

from leaderboard.dates import today_eastern
from leaderboard.models import Family, Member


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
