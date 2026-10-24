"""The MCP tools against a fake app, so each test can see exactly what was sent to the API and what came back."""

import asyncio
import json
import re
from datetime import date

import httpx
import pytest
from mcp import Client

from stepboard_mcp import server as server_module
from stepboard_mcp.api import StepboardApi
from stepboard_mcp.config import Config, LOCAL_API_URL
from stepboard_mcp.server import build_server, describe_board, find_member

TODAY = date(2026, 10, 24)  # a Saturday
BASE = "http://app.test"


class FakeApp:
    """The few endpoints the tools use, in memory. Boards are canned: ranking is the backend's job."""

    def __init__(self):
        self.families = [{"id": 1, "name": "Demo Family", "start_date": "2026-09-21"}]
        self.members = {1: [{"id": 1, "family_id": 1, "name": "Dad"}, {"id": 2, "family_id": 1, "name": "Mom"},
                            {"id": 3, "family_id": 1, "name": "Sam"}, {"id": 4, "family_id": 1, "name": "Samira"}]}
        self.steps = {}  # (member_id, day) -> steps
        self.posts = []
        self.requests = []
        self.reject_with = None  # (status, detail) for the next POST /steps

    def board(self, kind):
        totals = {m["id"]: sum(s for (mid, _), s in self.steps.items() if mid == m["id"]) for m in self.members[1]}
        order = sorted(self.members[1], key=lambda m: -totals[m["id"]])
        return {
            "kind": kind, "title": f"Test {kind} board", "start": "2026-10-19", "end": TODAY.isoformat(),
            "has_comparison": True, "callouts": [],
            "standings": [{"member_id": m["id"], "name": m["name"], "steps": totals[m["id"]], "rank": i + 1,
                           "medal": ["🥇", "🥈", "🥉"][i] if i < 3 else None, "prev_rank": None, "step_change": None}
                          for i, m in enumerate(order)],
        }

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(f"{request.method} {request.url.path}")
        path, q = request.url.path, request.url.params
        if path == "/families":
            return httpx.Response(200, json=self.families)
        if path == "/families/1/members":
            return httpx.Response(200, json=self.members[1])
        if path in ("/families/1/leaderboards/weekly", "/families/1/leaderboards/all-time"):
            board = self.board("weekly" if path.endswith("weekly") else "all_time")
            board["as_of_requested"] = q.get("as_of")
            return httpx.Response(200, json=board)
        if path.startswith("/members/") and path.endswith("/steps"):
            mid = int(path.split("/")[2])
            day = q.get("from")
            found = [{"member_id": mid, "day": day, "steps": self.steps[(mid, day)], "source": "manual"}] if (mid, day) in self.steps else []
            return httpx.Response(200, json=found)
        if path == "/steps" and request.method == "POST":
            body = json.loads(request.content)
            self.posts.append(body)
            if self.reject_with:
                status, detail = self.reject_with
                return httpx.Response(status, json={"detail": detail})
            for e in body["entries"]:
                self.steps[(body["member_id"], e["day"])] = e["steps"]
            return httpx.Response(200, json=[{"member_id": body["member_id"], "source": body["source"], **e} for e in body["entries"]])
        return httpx.Response(404, json={"detail": "Not found"})


@pytest.fixture
def app():
    return FakeApp()


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch):
    monkeypatch.setattr(server_module, "today_eastern", lambda: TODAY)


def make_server(app, family="Demo Family", transport=None):
    api = StepboardApi(BASE, client=httpx.Client(transport=transport or httpx.MockTransport(app.handle)))
    return build_server(Config(api_url=BASE, family=family), api=api)


def call(server, tool, args=None):
    """Calls a tool through a real MCP client, connected in-process. Returns (text, is_error)."""
    async def go():
        async with Client(server) as client:
            result = await client.call_tool(tool, args or {})
            return " ".join(c.text for c in result.content if hasattr(c, "text")), result.is_error
    return asyncio.run(go())


# --- What the assistant is told ------------------------------------------------------------------


def test_tools_and_their_marks(app):
    async def go():
        async with Client(make_server(app)) as client:
            return {t.name: t for t in (await client.list_tools()).tools}
    tools = asyncio.run(go())
    assert set(tools) == {"get_leaderboard", "list_members", "log_steps"}
    assert tools["get_leaderboard"].annotations.read_only_hint and tools["list_members"].annotations.read_only_hint
    log = tools["log_steps"].annotations
    assert (log.read_only_hint, log.destructive_hint, log.idempotent_hint) == (False, True, True)
    assert tools["log_steps"].input_schema["required"] == ["member", "steps"]


def test_instructions_name_the_family(app):
    assert "Family: Demo Family." in make_server(app).instructions


# --- Reading the boards --------------------------------------------------------------------------


def test_weekly_and_all_time_use_the_right_endpoints(app):
    call(make_server(app), "get_leaderboard")
    call(make_server(app), "get_leaderboard", {"board": "all_time", "as_of": "2026-10-18"})
    assert "GET /families/1/leaderboards/weekly" in app.requests
    assert "GET /families/1/leaderboards/all-time" in app.requests


def test_a_bad_date_is_refused_before_calling_the_board(app):
    text, is_error = call(make_server(app), "get_leaderboard", {"as_of": "last week"})
    assert is_error and "YYYY-MM-DD" in text
    assert not any("leaderboards" in r for r in app.requests)


def test_list_members(app):
    assert call(make_server(app), "list_members") == ("Demo Family has 4 members: Dad, Mom, Sam, Samira.", False)


def board(rows, has_comparison=True, callouts=()):
    return {"title": "📊 Week So Far — Oct 19–24", "has_comparison": has_comparison, "callouts": [{"text": c} for c in callouts],
            "standings": [dict(zip(["name", "steps", "rank", "medal", "prev_rank", "step_change"], r)) for r in rows]}


def test_describe_board_leader_movement_and_callouts():
    text = describe_board(board([("Alex", 71_756, 1, "🥇", 4, 1_550), ("Dad", 56_115, 2, "🥈", 1, -19_649), ("Kim", 0, 3, "🥉", None, None)],
                                callouts=["🔥 Best single day: Alex"]))
    assert text.splitlines() == [
        "📊 Week So Far — Oct 19–24",
        "Leader: Alex with 71,756 steps.",
        "🥇 Alex — 71,756 (up 3, +1,550 steps)",
        "🥈 Dad — 56,115 (down 1, -19,649 steps)",
        "🥉 Kim — 0 (new)",
        "🔥 Best single day: Alex",
    ]


@pytest.mark.parametrize(
    ("rows", "headline"),
    [
        ([("Ana", 5_000, 1, "🥇", None, None), ("Ben", 5_000, 1, "🥇", None, None)], "Tied for first: Ana and Ben, 5,000 steps each."),
        ([("Ana", 0, 1, "🥇", None, None)], "No steps logged yet."),
    ],
)
def test_describe_board_ties_and_empty_weeks(rows, headline):
    lines = describe_board(board(rows, has_comparison=False)).splitlines()
    assert lines[1] == headline
    assert "(" not in lines[2]  # no movement without a comparison


def test_describe_board_with_no_members():
    assert describe_board(board([])) == "📊 Week So Far — Oct 19–24\nNo one has joined yet."


# --- Finding members -----------------------------------------------------------------------------


MEMBERS = [{"id": 1, "name": "Dad"}, {"id": 2, "name": "Sam"}, {"id": 3, "name": "Samira"}, {"id": 4, "name": "Mom"}]


@pytest.mark.parametrize(("name", "found"), [("dad", "Dad"), (" SAM ", "Sam"), ("sami", "Samira"), ("mo", "Mom")])
def test_find_member(name, found):
    assert find_member(MEMBERS, name)["name"] == found


@pytest.mark.parametrize(("name", "message"), [("sa", '"sa" could be Sam, Samira. Which one?'),
                                                ("Chris", 'No member called "Chris". Members: Dad, Sam, Samira, Mom.')])
def test_find_member_asks_or_lists(name, message):
    with pytest.raises(Exception, match=re.escape(message)):
        find_member(MEMBERS, name)


# --- Logging steps -------------------------------------------------------------------------------


def test_log_steps_defaults_to_today_and_reports_the_rank(app):
    text, is_error = call(make_server(app), "log_steps", {"member": "dad", "steps": 30_000})
    assert not is_error
    assert app.posts == [{"member_id": 1, "source": "manual", "entries": [{"day": "2026-10-24", "steps": 30_000}]}]
    assert text == "Logged 30,000 steps for Dad on Saturday, Oct 24. This week Dad has 30,000 steps, rank 1 of 4."


def test_log_steps_says_when_it_replaced_a_total(app):
    app.steps[(1, "2026-10-24")] = 4_988
    text, _ = call(make_server(app), "log_steps", {"member": "Dad", "steps": 30_000})
    assert "replacing the 4,988 logged before" in text


def test_log_steps_says_when_nothing_changed(app):
    app.steps[(1, "2026-10-24")] = 30_000
    text, _ = call(make_server(app), "log_steps", {"member": "Dad", "steps": 30_000})
    assert "which it already was" in text


def test_a_day_before_this_week_has_no_rank_note(app):
    text, _ = call(make_server(app), "log_steps", {"member": "Mom", "steps": 12_000, "day": "2026-10-15"})
    assert text == "Logged 12,000 steps for Mom on Thursday, Oct 15."
    assert app.posts[0]["entries"] == [{"day": "2026-10-15", "steps": 12_000}]


@pytest.mark.parametrize("steps", [-1, 100_001])
def test_out_of_range_steps_never_reach_the_app(app, steps):
    _, is_error = call(make_server(app), "log_steps", {"member": "Dad", "steps": steps})
    assert is_error and app.posts == []


def test_an_ambiguous_name_logs_nothing(app):
    text, is_error = call(make_server(app), "log_steps", {"member": "sa", "steps": 1})
    assert is_error and "Which one?" in text and app.posts == []


def test_the_apps_own_message_is_passed_on(app):
    app.reject_with = (422, "entries: These days haven't happened yet: 2026-12-25.")
    text, is_error = call(make_server(app), "log_steps", {"member": "Dad", "steps": 1, "day": "2026-12-25"})
    assert is_error and "These days haven't happened yet: 2026-12-25." in text


# --- Settings and connection problems ------------------------------------------------------------


def test_an_unknown_family_lists_the_real_ones(app):
    text, is_error = call(make_server(app, family="Smiths"), "list_members")
    assert is_error and 'No family named "Smiths". Families: Demo Family.' in text


def test_the_app_not_running(app):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)
    text, is_error = call(make_server(app, transport=httpx.MockTransport(refuse)), "get_leaderboard")
    assert is_error and f"Can't reach the app at {BASE}" in text


def test_config_defaults_to_the_local_app_and_the_demo_family(monkeypatch):
    monkeypatch.delenv("STEPBOARD_API_URL", raising=False)
    monkeypatch.delenv("STEPBOARD_FAMILY", raising=False)
    assert Config.from_env() == Config(api_url=LOCAL_API_URL, family="Demo Family")
    monkeypatch.setenv("STEPBOARD_API_URL", "https://159-89-228-242.sslip.io/api/")
    monkeypatch.setenv("STEPBOARD_FAMILY", "Spencers")
    assert Config.from_env() == Config(api_url="https://159-89-228-242.sslip.io/api", family="Spencers")
