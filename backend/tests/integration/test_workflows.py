"""Whole user journeys through the HTTP API, the way the React app and a reviewer use it.

Each test goes across several endpoints and checks what a person would see, so it catches breaks in how the
parts fit together that single-endpoint tests can miss.
"""

from datetime import date, timedelta
from io import StringIO

import httpx
import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 14)  # a Wednesday
MONDAY = date(2026, 10, 12)
LAST_MONDAY = MONDAY - timedelta(days=7)


@pytest.fixture(autouse=True)
def today(monkeypatch):
    """Every part of the app asks today_eastern(), which asks Django's clock; pin that clock."""
    monkeypatch.setattr("leaderboard.dates.timezone.localdate", lambda *args, **kwargs: TODAY)


class Api:
    """The calls the React app makes (frontend/src/api.js), without the /api prefix nginx adds."""

    def __init__(self, client):
        self.client = client

    def get(self, path, code=None, **params):
        # The test client sends a family's code for /families/{id}/... by itself; /family needs one given.
        headers = {"X-Family-Code": code} if code else None
        response = self.client.get(path, params, headers=headers)
        assert response.status_code == 200, (path, response.status_code, response.content)
        return response.json()

    def post(self, path, body, expect=(200, 201)):
        response = self.client.post(path, body, content_type="application/json")
        assert response.status_code in expect, (path, response.status_code, response.content)
        return response.json()

    def log(self, member_id, first_day, steps_per_day, source="manual"):
        entries = [{"day": (first_day + timedelta(days=i)).isoformat(), "steps": s} for i, s in enumerate(steps_per_day)]
        return self.post("/steps", {"member_id": member_id, "source": source, "entries": entries})


@pytest.fixture
def api(client):
    return Api(client)


def run_command(*args):
    """A management command, as the container or the scheduler runs it; its printed summary isn't needed."""
    call_command(*args, stdout=StringIO())


def rows(board):
    return [(s["medal"] or f"{s['rank']}.", s["name"], s["steps"]) for s in board["standings"]]


def test_a_reviewers_first_visit(api):
    """The README's walkthrough: the demo is already there, join it, log steps, climb the board, send a digest."""
    run_command("seed_demo")  # what the container does on start

    demo = api.get("/family", code="DEMO")  # what the app does on a first visit: the Demo Family's code is public
    assert demo["name"] == "Demo Family"
    board = api.get(f"/families/{demo['id']}/leaderboards/weekly")
    assert board["title"] == "📊 Week So Far — Oct 12–14"
    assert [s["medal"] for s in board["standings"]][:3] == ["🥇", "🥈", "🥉"]
    assert board["callouts"]

    me = api.post("/families/join", {"invite_code": "demo", "name": "Reviewer"})
    api.log(me["id"], TODAY, [60_000])

    board = api.get(f"/families/{demo['id']}/leaderboards/weekly")
    top = board["standings"][0]
    assert (top["name"], top["medal"], top["steps"], top["prev_rank"]) == ("Reviewer", "🥇", 60_000, None)
    assert "Reviewer, 60,000 on Wednesday" in " ".join(c["text"] for c in board["callouts"])
    assert api.get(f"/members/{me['id']}/steps") == [
        {"member_id": me["id"], "day": TODAY.isoformat(), "steps": 60_000, "source": "manual"}
    ]

    digest = api.post(f"/families/{demo['id']}/digests", {"kind": "weekly"})
    assert digest["discord_status"] == "not_configured"
    assert "🥇 Reviewer — 60,000 (new)" in digest["text"]
    assert api.get(f"/families/{demo['id']}/messages")[0] == digest


def test_a_new_familys_first_two_weeks(api):
    family = api.post("/families", {"name": "Spencers", "start_date": LAST_MONDAY.isoformat()})
    ana = api.post("/families/join", {"invite_code": family["invite_code"], "name": "Ana"})
    ben = api.post("/families/join", {"invite_code": family["invite_code"].lower(), "name": "Ben"})
    assert [m["name"] for m in api.get(f"/families/{family['id']}/members")] == ["Ana", "Ben"]

    # Week one: Ana leads. Nothing to compare with yet.
    api.log(ana["id"], LAST_MONDAY, [10_000] * 7)
    api.log(ben["id"], LAST_MONDAY, [8_000] * 6 + [18_000])
    week_one = api.get(f"/families/{family['id']}/leaderboards/weekly", as_of="2026-10-11")
    assert week_one["title"] == "🏆 Weekly Steps — Oct 5–11"
    assert rows(week_one) == [("🥇", "Ana", 70_000), ("🥈", "Ben", 66_000)]
    assert not week_one["has_comparison"]
    assert [c["text"] for c in week_one["callouts"]] == ["🔥 Best single day: Ben, 18,000 on Sunday"]

    # Week two so far (Mon–Wed): Ben overtakes, compared with the same three days of week one.
    api.log(ana["id"], MONDAY, [9_000] * 3)
    api.log(ben["id"], MONDAY, [15_000] * 3)
    week_two = api.get(f"/families/{family['id']}/leaderboards/weekly")
    assert week_two["title"] == "📊 Week So Far — Oct 12–14"
    assert rows(week_two) == [("🥇", "Ben", 45_000), ("🥈", "Ana", 27_000)]
    ben_row, ana_row = week_two["standings"]
    assert (ben_row["prev_rank"], ben_row["step_change"]) == (2, 45_000 - 24_000)
    assert (ana_row["prev_rank"], ana_row["step_change"]) == (1, 27_000 - 30_000)
    assert "🚀 Most improved: Ben, +21,000 from last week" in [c["text"] for c in week_two["callouts"]]

    # All-time: everything since the start date. Its first month has no comparison.
    all_time = api.get(f"/families/{family['id']}/leaderboards/all-time")
    assert all_time["title"] == "🏅 All-time Steps — since Oct 5, 2026"
    assert rows(all_time) == [("🥇", "Ben", 66_000 + 45_000), ("🥈", "Ana", 70_000 + 27_000)]
    assert not all_time["has_comparison"]


def test_logging_a_day_again_changes_the_board_not_adds_to_it(api):
    family = api.post("/families", {"name": "Fixers", "start_date": MONDAY.isoformat()})
    me = api.post("/families/join", {"invite_code": family["invite_code"], "name": "Chris"})

    api.log(me["id"], TODAY, [5_000])
    api.log(me["id"], TODAY, [12_000], source="import")  # a correction, or a watch syncing later

    assert rows(api.get(f"/families/{family['id']}/leaderboards/weekly")) == [("🥇", "Chris", 12_000)]
    assert [(e["steps"], e["source"]) for e in api.get(f"/members/{me['id']}/steps")] == [(12_000, "import")]


def test_an_import_shows_up_everywhere(api):
    family = api.post("/families", {"name": "Importers", "start_date": "2026-10-01"})
    me = api.post("/families/join", {"invite_code": family["invite_code"], "name": "Sam"})
    first = TODAY - timedelta(days=9)
    days = [6_000, 7_000, 8_000, 9_000, 15_000, 10_000, 11_000, 12_000, 13_000, 14_000]
    api.log(me["id"], first, days, source="shortcut")

    history = api.get(f"/members/{me['id']}/steps")
    assert [e["steps"] for e in history] == list(reversed(days))  # newest first
    assert {e["source"] for e in history} == {"shortcut"}

    all_time = api.get(f"/families/{family['id']}/leaderboards/all-time")
    assert rows(all_time) == [("🥇", "Sam", sum(days))]
    assert all_time["callouts"][0]["text"] == "🔥 Best day ever: Sam, 15,000 on Oct 9, 2026"

    # This week (Mon–Wed) counts only its own three days.
    assert rows(api.get(f"/families/{family['id']}/leaderboards/weekly")) == [("🥇", "Sam", 12_000 + 13_000 + 14_000)]


def test_a_bad_import_changes_nothing_anywhere(api):
    family = api.post("/families", {"name": "Careful", "start_date": MONDAY.isoformat()})
    me = api.post("/families/join", {"invite_code": family["invite_code"], "name": "Alex"})
    api.log(me["id"], MONDAY, [4_000])

    bad = [{"day": MONDAY.isoformat(), "steps": 9_000}, {"day": TODAY.isoformat(), "steps": 100_001}]
    api.post("/steps", {"member_id": me["id"], "entries": bad}, expect=(422,))

    assert rows(api.get(f"/families/{family['id']}/leaderboards/weekly")) == [("🥇", "Alex", 4_000)]
    assert len(api.get(f"/members/{me['id']}/steps")) == 1


def test_a_digest_reaches_discord_and_the_messages_page(api, settings, monkeypatch):
    sent = []

    def fake_discord(url, json, timeout):
        sent.append(json)
        return httpx.Response(204, request=httpx.Request("POST", url))

    settings.DISCORD_WEBHOOK_URL = "https://discord.test/api/webhooks/1/token"
    monkeypatch.setattr("leaderboard.discord.httpx.post", fake_discord)

    # Another family exists first, so a digest built from the wrong family would show the wrong people.
    neighbors = api.post("/families", {"name": "Neighbors", "start_date": MONDAY.isoformat()})
    neighbor = api.post("/families/join", {"invite_code": neighbors["invite_code"], "name": "Pat"})
    api.log(neighbor["id"], MONDAY, [20_000])

    family = api.post("/families", {"name": "Posters", "start_date": MONDAY.isoformat()})
    me = api.post("/families/join", {"invite_code": family["invite_code"], "name": "Kim"})
    api.log(me["id"], MONDAY, [7_000, 8_000, 9_000])

    digest = api.post(f"/families/{family['id']}/digests", {"kind": "weekly"})
    assert digest["discord_status"] == "sent"
    assert [post["content"] for post in sent] == [digest["text"]]
    assert "🥇 Kim — 24,000" in digest["text"]
    assert "Pat" not in digest["text"]
    assert digest["family_id"] == family["id"]
    assert api.get(f"/families/{family['id']}/messages") == [digest]
    assert api.get(f"/families/{neighbors['id']}/messages") == []


def test_scheduled_digests_appear_in_the_app(api):
    """The Monday job, run by hand: every real family gets one digest, visible in the app; a rerun adds none."""
    run_command("seed_demo")
    family = api.post("/families", {"name": "Spencers", "start_date": LAST_MONDAY.isoformat()})
    me = api.post("/families/join", {"invite_code": family["invite_code"], "name": "Chris"})
    api.log(me["id"], MONDAY, [10_000, 11_000])

    run_command("send_digests", "weekly")  # counts through yesterday

    messages = api.get(f"/families/{family['id']}/messages")
    assert len(messages) == 1
    assert messages[0]["text"].splitlines()[:2] == ["📊 Week So Far — Oct 12–13", "🥇 Chris — 21,000 (new)"]
    demo = api.get("/family", code="DEMO")
    assert api.get(f"/families/{demo['id']}/messages") == []  # skipped: the scheduler leaves the Demo Family out

    run_command("send_digests", "weekly")
    assert len(api.get(f"/families/{family['id']}/messages")) == 1


def test_a_familys_code_keeps_outsiders_out_and_can_be_replaced(plain_client):
    """Invite code as the family's password (security/pr-audit.md, finding 2), as a family would meet it."""
    def call(method, path, code=None, body=None):
        headers = {"X-Family-Code": code} if code else None
        if method == "get":
            return plain_client.get(path, headers=headers)
        return plain_client.post(path, body or {}, content_type="application/json", headers=headers)

    family = call("post", "/families", body={"name": "Spencers"}).json()
    code, fid = family["invite_code"], family["id"]
    me = call("post", "/families/join", body={"invite_code": code.lower(), "name": "Chris"}).json()
    assert call("post", "/steps", code, {"member_id": me["id"], "entries": [{"day": TODAY.isoformat(), "steps": 9_000}]}).status_code == 200

    # An outsider: no code, then a guess. Neither gets the board, nor can log steps for Chris.
    assert call("get", f"/families/{fid}/leaderboards/weekly").status_code == 401
    assert call("get", f"/families/{fid}/leaderboards/weekly", "WRONG2").status_code == 403
    assert call("post", "/steps", "WRONG2", {"member_id": me["id"], "entries": [{"day": TODAY.isoformat(), "steps": 1}]}).status_code == 403
    assert call("get", "/family", code).json() == {"id": fid, "name": "Spencers", "start_date": TODAY.isoformat()}

    # The code was shared too widely: the family makes a new one.
    replaced = call("post", f"/families/{fid}/invite-code", code)
    assert replaced.status_code == 200
    new_code = replaced.json()["invite_code"]
    assert new_code != code

    # The old code stops working at once, for reading and for joining; the new one works, and Chris is still in.
    assert call("get", f"/families/{fid}/members", code).status_code == 403
    assert call("post", "/families/join", body={"invite_code": code, "name": "Stranger"}).status_code == 404
    assert [m["name"] for m in call("get", f"/families/{fid}/members", new_code).json()] == ["Chris"]
    board = call("get", f"/families/{fid}/leaderboards/weekly", new_code).json()
    assert [(s["name"], s["steps"]) for s in board["standings"]] == [("Chris", 9_000)]
