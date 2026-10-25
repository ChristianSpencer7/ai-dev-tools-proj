import json
import re

import pytest
from django.core.cache import cache
from django.test import Client

TEST_FOLDERS = ("unit", "integration")

# Sent for a family or member that doesn't exist, so the request gets its 404 rather than the 401 for no code.
NO_SUCH_FAMILY_CODE = "NOSUCH"


class FamilyCodeClient(Client):
    """A test client that sends the right X-Family-Code by itself, so each test can be about what it tests.

    For /families/{id}/..., /members/{id}/... and POST /steps it looks up whose family the request is about and
    sends that family's code, unless the test passes a code itself. The access checks it skips are tested on their
    own, with a plain client, in tests/integration/test_access.py.
    """

    def generic(self, method, path, data="", content_type="application/octet-stream", secure=False, *,
                headers=None, query_params=None, **extra):
        headers = dict(headers or {})
        if "X-Family-Code" not in headers and "HTTP_X_FAMILY_CODE" not in extra:
            code = code_for_request(path, data, content_type)
            if code:
                headers["X-Family-Code"] = code
        return super().generic(method, path, data, content_type, secure, headers=headers,
                               query_params=query_params, **extra)


def code_for_request(path: str, body, content_type: str) -> str | None:
    from leaderboard.models import Family, Member

    if match := re.match(r"^/families/(\d+)(/|$)", path):
        family = Family.objects.filter(pk=match.group(1)).first()
        return family.invite_code if family else NO_SUCH_FAMILY_CODE
    member_id = None
    if match := re.match(r"^/members/(\d+)(/|$)", path):
        member_id = match.group(1)
    elif path.rstrip("/") == "/steps":
        try:
            member_id = json.loads(body or "{}").get("member_id")
        except (ValueError, AttributeError):
            member_id = None
        if member_id is None:  # a body without a member: send a code anyway, so the test reaches its 422
            return NO_SUCH_FAMILY_CODE
    if member_id is not None:
        member = Member.objects.select_related("family").filter(pk=member_id).first() if str(member_id).isdigit() else None
        return member.family.invite_code if member else NO_SUCH_FAMILY_CODE
    return None


@pytest.fixture
def client():
    """pytest-django's client, sending family codes by itself (FamilyCodeClient)."""
    return FamilyCodeClient()


@pytest.fixture
def plain_client():
    """A client that sends no family code unless a test passes one: for testing the access checks themselves."""
    return Client()


@pytest.fixture(autouse=True)
def fresh_wrong_code_counts():
    """Wrong-code counts live in the cache (leaderboard/access.py); one test's refusals mustn't block the next."""
    cache.clear()
    yield
    cache.clear()


def pytest_collection_modifyitems(items):
    """Marks each test by its folder, so `pytest -m unit` and `pytest -m integration` work too.

    CI runs tests/unit and tests/integration separately, so a test anywhere else would never run there.
    """
    for item in items:
        folder = item.path.parent.name
        if folder not in TEST_FOLDERS:
            raise pytest.UsageError(f"{item.path.name}: put tests in tests/unit or tests/integration (see tests/README.md)")
        item.add_marker(folder)


@pytest.fixture(autouse=True)
def no_real_discord(settings, monkeypatch):
    """Tests never post to a real Discord channel, even with DISCORD_WEBHOOK_URL in .env.

    The webhook is cleared, and any request that still slips through fails the test. Tests that need
    Discord use the fake_discord fixture in test_digests.py instead.
    """
    settings.DISCORD_WEBHOOK_URL = None

    def refuse(*args, **kwargs):
        raise AssertionError("A test tried to reach Discord for real")

    monkeypatch.setattr("leaderboard.discord.httpx.post", refuse)
