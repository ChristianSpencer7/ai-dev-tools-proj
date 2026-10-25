"""The invite code as the family's password: every request about a family sends its code (openapi.yaml, FamilyCode).

The checks run in the contract's order: no code is 401; an unknown family or member is 404; another family's code
is 403. Wrong codes are counted per client, and after WRONG_CODE_LIMIT of them in WINDOW_SECONDS the client gets
429 until the window ends, so codes can't be guessed (about a billion of them: invites.py). The count lives in
Django's cache, which is per process; with gunicorn's 2 workers the real limit is up to twice this, still hopeless
for guessing.
"""

import ipaddress

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.request import Request

from leaderboard.models import Family, Member

HEADER = "X-Family-Code"
WINDOW_SECONDS = 60


class NoCode(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = f"This needs the family's invite code, in the {HEADER} header"


class WrongCode(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "That invite code isn't this family's"


class TooManyWrongCodes(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many wrong invite codes; try again in a minute"


def client_address(request: Request) -> str:
    """Who's asking, for counting wrong codes.

    In production every request reaches Django from nginx, so REMOTE_ADDR is the same for everyone. Caddy puts the
    visitor's address in X-Forwarded-For, replacing anything the visitor sent, so the last public address there is
    the visitor's. Locally there's none, and REMOTE_ADDR is used.
    """
    forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    for candidate in reversed(forwarded):
        try:
            if not ipaddress.ip_address(candidate).is_private:
                return candidate
        except ValueError:
            continue
    return request.META.get("REMOTE_ADDR", "unknown")


def _failures_key(request: Request) -> str:
    return f"wrong-codes:{client_address(request)}"


def check_not_blocked(request: Request) -> None:
    if cache.get(_failures_key(request), 0) >= settings.WRONG_CODE_LIMIT:
        raise TooManyWrongCodes()


def record_wrong_code(request: Request) -> None:
    key = _failures_key(request)
    if cache.add(key, 1, WINDOW_SECONDS):  # the first in this window starts it
        return
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.add(key, 1, WINDOW_SECONDS)


def code_from(request: Request) -> str:
    """The code sent, in capitals (codes are stored that way, so "demo" works), or 401 if there's none."""
    code = request.headers.get(HEADER, "").strip().upper()
    if not code:
        raise NoCode()
    check_not_blocked(request)
    return code


def _matches(request: Request, family: Family, code: str) -> None:
    if family.invite_code != code:
        record_wrong_code(request)
        raise WrongCode()


def family_for(request: Request, family_id: int) -> Family:
    """The family in the URL, if the request has its code."""
    code = code_from(request)
    try:
        family = Family.objects.get(pk=family_id)
    except Family.DoesNotExist:
        raise NotFound("Family not found")
    _matches(request, family, code)
    return family


def member_for(request: Request, member_id: int, code: str | None = None) -> Member:
    """The member, if the request has their family's code."""
    code = code or code_from(request)
    try:
        member = Member.objects.select_related("family").get(pk=member_id)
    except Member.DoesNotExist:
        raise NotFound("Member not found")
    _matches(request, member.family, code)
    return member


def family_for_code(request: Request) -> Family:
    """GET /family: the family this code opens, or 403."""
    code = code_from(request)
    family = Family.objects.filter(invite_code=code).first()
    if family is None:
        record_wrong_code(request)
        raise WrongCode("No family has that invite code")
    return family
