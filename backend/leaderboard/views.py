from django.db import connection, transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from leaderboard.access import check_not_blocked, code_from, family_for, family_for_code, member_for, record_wrong_code
from leaderboard.boards import alltime_board, weekly_board
from leaderboard.digests import send_digest
from leaderboard.invites import unique_invite_code
from leaderboard.models import Family, Member, StepEntry
from leaderboard.seed import DEMO_INVITE_CODE
from leaderboard.serializers import (
    AsOfQuerySerializer,
    DigestRequestSerializer,
    FamilyCreateSerializer,
    FamilySerializer,
    FamilySummarySerializer,
    JoinRequestSerializer,
    LeaderboardSerializer,
    MemberSerializer,
    MessageSerializer,
    StepEntrySerializer,
    StepHistoryQuerySerializer,
    StepsImportSerializer,
)

# Every view about a family gets it through leaderboard/access.py, which checks the X-Family-Code header first.


@api_view(["GET", "HEAD"])
def health(request: Request) -> Response:
    """Liveness check: the backend is up and can reach the database. HEAD too, for uptime monitors."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"ok": True})


@api_view(["POST"])
def families(request: Request) -> Response:
    """Creates a family and returns its code: the one response that shows a new family's code. There's no list."""
    serializer = FamilyCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    family = serializer.save(invite_code=unique_invite_code())
    return Response(FamilySerializer(family).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def family_for_this_code(request: Request) -> Response:
    """The family the X-Family-Code header opens: how a client with only a code finds its family."""
    return Response(FamilySummarySerializer(family_for_code(request)).data)


@api_view(["GET"])
def family_detail(request: Request, family_id: int) -> Response:
    """Without the invite code, which the caller already has."""
    return Response(FamilySummarySerializer(family_for(request, family_id)).data)


@api_view(["POST"])
def new_invite_code(request: Request, family_id: int) -> Response:
    """Replaces the family's code; the old one stops working at once. The Demo Family's stays DEMO."""
    family = family_for(request, family_id)
    if family.invite_code == DEMO_INVITE_CODE:
        raise ValidationError("The Demo Family's invite code can't be changed: it's public on purpose.")
    family.invite_code = unique_invite_code()
    family.save(update_fields=["invite_code"])
    return Response(FamilySerializer(family).data)


@api_view(["GET"])
def family_members(request: Request, family_id: int) -> Response:
    """Members ordered by name (Member.Meta.ordering)."""
    family = family_for(request, family_id)
    return Response(MemberSerializer(family.members.all(), many=True).data)


@api_view(["POST"])
def join_family(request: Request) -> Response:
    """Adds a member to the family with this invite code. The serializer has already uppercased it.

    The code is in the body, not the header. A wrong one counts toward the wrong-code limit, like a wrong header.
    """
    check_not_blocked(request)
    serializer = JoinRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    family = Family.objects.filter(invite_code=serializer.validated_data["invite_code"]).first()
    if family is None:
        record_wrong_code(request)
        raise NotFound("No family has that invite code")
    member = Member.objects.create(family=family, name=serializer.validated_data["name"])
    return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def log_steps(request: Request) -> Response:
    """Records daily totals. Logging a day again replaces its total; a bad request saves nothing.

    Returns 200, not 201, because a request can update existing entries as well as create new ones.
    No code is 401 before anything else; the body is checked next, then the member it names (404, or 403).
    """
    code = code_from(request)
    serializer = StepsImportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # every entry is checked before anything is saved
    data = serializer.validated_data
    member = member_for(request, data["member_id"], code)

    with transaction.atomic():
        saved = [
            StepEntry.objects.update_or_create(
                member=member,
                day=entry["day"],
                defaults={"steps": entry["steps"], "source": data["source"]},
            )[0]
            for entry in data["entries"]
        ]
    return Response(StepEntrySerializer(saved, many=True).data)


@api_view(["GET"])
def member_steps(request: Request, member_id: int) -> Response:
    """A member's daily totals from `from` through `to`, newest first (StepEntry.Meta.ordering).

    Defaults to the last 14 days ending today, Eastern. The member (and their family's code) is checked before the dates.
    """
    member = member_for(request, member_id)
    query = StepHistoryQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    days = query.validated_data
    entries = member.steps.filter(day__range=(days["from"], days["to"]))
    return Response(StepEntrySerializer(entries, many=True).data)


def leaderboard_response(request: Request, family_id: int, build_board) -> Response:
    """Shared by both boards: the family and its code first, then 422 for a bad as_of."""
    family = family_for(request, family_id)
    query = AsOfQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return Response(LeaderboardSerializer(build_board(family, query.validated_data["as_of"])).data)


@api_view(["GET"])
def weekly_leaderboard(request: Request, family_id: int) -> Response:
    """The week (Monday–Sunday) containing as_of, counted through as_of."""
    return leaderboard_response(request, family_id, weekly_board)


@api_view(["GET"])
def alltime_leaderboard(request: Request, family_id: int) -> Response:
    """Everything from the family's start date through as_of."""
    return leaderboard_response(request, family_id, alltime_board)


@api_view(["GET"])
def family_messages(request: Request, family_id: int) -> Response:
    """The family's saved digests, newest first (Message.Meta.ordering)."""
    family = family_for(request, family_id)
    return Response(MessageSerializer(family.messages.all(), many=True).data)


@api_view(["POST"])
def create_digest(request: Request, family_id: int) -> Response:
    """Builds a weekly or monthly digest, posts it to Discord if a webhook is set, and saves it.

    Used by the app's "Send digest now" (as_of defaults to today) and by the scheduler (task 8). The Demo Family's
    are never posted: send_digest leaves it out.
    """
    family = family_for(request, family_id)
    serializer = DigestRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    message = send_digest(family, serializer.validated_data["kind"], serializer.validated_data["as_of"])
    return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
