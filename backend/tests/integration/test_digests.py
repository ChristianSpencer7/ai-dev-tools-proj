"""Digests and the Messages page: saving, Discord posting (always faked), and the two endpoints."""

import logging
from datetime import date

import httpx
import pytest

from leaderboard.boards import alltime_board, weekly_board
from leaderboard.dates import today_eastern
from leaderboard.models import Family, Member, Message
from leaderboard.seed import seed_demo_family

pytestmark = pytest.mark.django_db

SEEDED_ON = date(2026, 10, 14)  # a Wednesday
LAST_SUNDAY = date(2026, 10, 11)
WEBHOOK = "https://discord.test/api/webhooks/123/SECRET-TOKEN"


@pytest.fixture
def demo():
    return seed_demo_family(SEEDED_ON)


@pytest.fixture
def real_family():
    """The demo's data under an ordinary code: a family whose digests do go to Discord (the Demo Family's never do)."""
    family = seed_demo_family(SEEDED_ON)
    family.invite_code = "SPEN23"
    family.save(update_fields=["invite_code"])
    return family


class FakeDiscord:
    """Stands in for httpx.post. Set `result` to an HTTP status code, or to an exception to raise."""

    def __init__(self):
        self.calls = []
        self.result = 204

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if isinstance(self.result, Exception):
            raise self.result
        return httpx.Response(self.result, request=httpx.Request("POST", url))


@pytest.fixture
def fake_discord(settings, monkeypatch):
    settings.DISCORD_WEBHOOK_URL = WEBHOOK
    fake = FakeDiscord()
    monkeypatch.setattr("leaderboard.discord.httpx.post", fake.post)
    return fake


def send(client, family_id, **body):
    return client.post(f"/families/{family_id}/digests", body, content_type="application/json")


# --- The three Discord outcomes --------------------------------------------------------------------


def test_without_a_webhook_the_digest_is_only_saved(client, demo):
    response = send(client, demo.id, kind="weekly", as_of=LAST_SUNDAY.isoformat())
    assert response.status_code == 201
    body = response.json()
    assert body["discord_status"] == "not_configured"
    assert body["text"] == weekly_board(demo, LAST_SUNDAY).text()
    assert Message.objects.get(pk=body["id"]).text == body["text"]


def test_with_a_webhook_the_digest_is_posted(client, real_family, fake_discord):
    body = send(client, real_family.id, kind="weekly", as_of=LAST_SUNDAY.isoformat()).json()
    assert body["discord_status"] == "sent"
    assert len(fake_discord.calls) == 1
    call = fake_discord.calls[0]
    assert call["url"] == WEBHOOK
    assert call["json"] == {"content": body["text"], "allowed_mentions": {"parse": []}}
    assert call["timeout"] > 0


@pytest.mark.parametrize(
    "result",
    [500, 404, 429, httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.InvalidURL("bad")],
    ids=["server error", "webhook deleted", "rate limited", "timeout", "no connection", "bad URL"],
)
def test_a_failed_post_is_recorded_and_the_digest_kept(client, real_family, fake_discord, caplog, result):
    fake_discord.result = result
    with caplog.at_level(logging.WARNING, logger="leaderboard.discord"):
        response = send(client, real_family.id, kind="weekly")
    assert response.status_code == 201
    assert response.json()["discord_status"] == "failed"
    assert Message.objects.filter(pk=response.json()["id"]).exists()
    assert "Discord webhook post failed" in caplog.text
    assert "SECRET-TOKEN" not in caplog.text and "discord.test" not in caplog.text  # the URL is never logged


def test_the_demo_familys_digest_is_never_posted_even_with_a_webhook(client, demo, fake_discord):
    """Anyone can send the Demo Family a digest (its code is public), and the webhook is a real family's channel."""
    for _ in range(3):
        body = send(client, demo.id, kind="weekly").json()
        assert body["discord_status"] == "not_configured"
    assert fake_discord.calls == []
    assert Message.objects.filter(family=demo).count() == 3  # still saved for the Messages page


# --- What goes into a digest ---------------------------------------------------------------------


def test_monthly_digest_uses_the_all_time_board(client, demo):
    body = send(client, demo.id, kind="monthly", as_of="2026-09-30").json()
    assert body["kind"] == "monthly"
    assert body["text"] == alltime_board(demo, date(2026, 9, 30)).text()
    assert body["text"].startswith("🏅 All-time Steps")


def test_as_of_defaults_to_today(client, demo):
    body = send(client, demo.id, kind="weekly").json()
    assert body["text"] == weekly_board(demo, today_eastern()).text()


def test_a_family_with_no_members_still_gets_a_digest(client):
    empty = Family.objects.create(name="New", start_date=date(2026, 10, 1), invite_code="EMPTY1")
    body = send(client, empty.id, kind="weekly", as_of="2026-10-04").json()
    assert body["text"] == "🏆 Weekly Steps — Sep 28–Oct 4\nNo one has joined yet."


def test_long_digests_are_cut_for_discord_but_saved_in_full(client, fake_discord):
    big = Family.objects.create(name="Big", start_date=date(2026, 10, 1), invite_code="BIG001")
    Member.objects.bulk_create(Member(family=big, name=f"Cousin number {n:03}") for n in range(100))
    body = send(client, big.id, kind="weekly", as_of="2026-10-04").json()
    posted = fake_discord.calls[0]["json"]["content"]
    assert len(body["text"]) > 2_000
    assert len(posted) == 2_000 and posted.endswith("…")
    assert Message.objects.get(pk=body["id"]).text == body["text"]


def test_member_names_cannot_ping_the_channel(client, fake_discord):
    family = Family.objects.create(name="Pranksters", start_date=date(2026, 10, 1), invite_code="PRANK1")
    Member.objects.create(family=family, name="@everyone")
    send(client, family.id, kind="weekly", as_of="2026-10-04")
    payload = fake_discord.calls[0]["json"]
    assert "@everyone" in payload["content"]
    assert payload["allowed_mentions"] == {"parse": []}  # Discord shows the name but notifies nobody


# --- GET /families/{id}/messages -----------------------------------------------------------------


def test_messages_are_listed_newest_first(client, demo):
    first = send(client, demo.id, kind="weekly", as_of=LAST_SUNDAY.isoformat()).json()
    second = send(client, demo.id, kind="monthly").json()
    listed = client.get(f"/families/{demo.id}/messages").json()
    assert [m["id"] for m in listed] == [second["id"], first["id"]]
    assert listed[0] == second
    assert set(listed[0]) == {"id", "family_id", "kind", "text", "created_at", "discord_status"}


def test_messages_belong_to_their_family(client, demo):
    other = Family.objects.create(name="Neighbors", start_date=date(2026, 10, 1), invite_code="OTHER1")
    send(client, other.id, kind="weekly")
    assert client.get(f"/families/{demo.id}/messages").json() == []
    assert len(client.get(f"/families/{other.id}/messages").json()) == 1


# --- Errors --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({}, "kind: This field is required."),
        ({"kind": "daily"}, 'kind: "daily" is not a valid choice.'),
        ({"kind": "weekly", "as_of": "yesterday"}, "as_of: Date has wrong format. Use one of these formats instead: YYYY-MM-DD."),
    ],
)
def test_bad_requests_are_422_and_save_nothing(client, demo, body, detail):
    response = send(client, demo.id, **body)
    assert (response.status_code, response.json()) == (422, {"detail": detail})
    assert not Message.objects.exists()


def test_unknown_family(client):
    for response in [send(client, 999, kind="daily"), client.get("/families/999/messages")]:
        assert (response.status_code, response.json()) == (404, {"detail": "Family not found"})


def test_wrong_methods(client, demo):
    assert client.get(f"/families/{demo.id}/digests").status_code == 405
    assert client.post(f"/families/{demo.id}/messages").status_code == 405
