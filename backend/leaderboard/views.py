from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from leaderboard.invites import unique_invite_code
from leaderboard.models import Family, Member
from leaderboard.serializers import (
    FamilyCreateSerializer,
    FamilySerializer,
    FamilySummarySerializer,
    JoinRequestSerializer,
    MemberSerializer,
)


def get_family(family_id: int) -> Family:
    try:
        return Family.objects.get(pk=family_id)
    except Family.DoesNotExist:
        raise NotFound("Family not found")


@api_view(["GET"])
def health(request: Request) -> Response:
    """Liveness check: the backend is up and can reach the database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"ok": True})


@api_view(["GET", "POST"])
def families(request: Request) -> Response:
    """GET lists families without invite codes; POST creates one and returns its code."""
    if request.method == "GET":
        return Response(FamilySummarySerializer(Family.objects.order_by("id"), many=True).data)

    serializer = FamilyCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    family = serializer.save(invite_code=unique_invite_code())
    return Response(FamilySerializer(family).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def family_detail(request: Request, family_id: int) -> Response:
    return Response(FamilySerializer(get_family(family_id)).data)


@api_view(["GET"])
def family_members(request: Request, family_id: int) -> Response:
    """Members ordered by name (Member.Meta.ordering)."""
    family = get_family(family_id)
    return Response(MemberSerializer(family.members.all(), many=True).data)


@api_view(["POST"])
def join_family(request: Request) -> Response:
    """Adds a member to the family with this invite code. The serializer has already uppercased it."""
    serializer = JoinRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    family = Family.objects.filter(invite_code=serializer.validated_data["invite_code"]).first()
    if family is None:
        raise NotFound("No family has that invite code")
    member = Member.objects.create(family=family, name=serializer.validated_data["name"])
    return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)
