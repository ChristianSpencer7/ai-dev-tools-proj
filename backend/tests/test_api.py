from datetime import date, timedelta

import httpx
import pytest

from stepboard import digests
from stepboard.config import today_eastern


@pytest.fixture
def joined(client):
    """A family started two weeks ago, with one member."""
    start = today_eastern() - timedelta(days=14)
    family = client.post("/families", json={"name": "Spencers", "start_date": start.isoformat()}).json()
    member = client.post("/families/join", json={"invite_code": family["invite_code"].lower(), "name": "Chris"}).json()
    return family, member


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_create_and_join_family(client, joined):
    family, member = joined
    assert len(family["invite_code"]) == 6
    assert member["family_id"] == family["id"]
    assert client.get(f"/families/{family['id']}/members").json() == [member]
    assert "invite_code" not in client.get("/families").json()[0]


def test_join_with_unknown_code(client):
    response = client.post("/families/join", json={"invite_code": "NOPE", "name": "X"})
    assert response.status_code == 404


def test_log_steps_replaces_same_day(client, joined):
    _, member = joined
    today = today_eastern().isoformat()
    client.post("/steps", json={"member_id": member["id"], "entries": [{"day": today, "steps": 4_000}]})
    client.post("/steps", json={"member_id": member["id"], "entries": [{"day": today, "steps": 9_000}]})
    entries = client.get(f"/members/{member['id']}/steps").json()
    assert entries == [{"member_id": member["id"], "day": today, "steps": 9_000, "source": "manual"}]


def test_import_several_days(client, joined):
    _, member = joined
    days = [(today_eastern() - timedelta(days=n)).isoformat() for n in range(3)]
    body = {"member_id": member["id"], "source": "import", "entries": [{"day": d, "steps": 5_000} for d in days]}
    assert len(client.post("/steps", json=body).json()) == 3


@pytest.mark.parametrize(
    "entry",
    [
        {"day": (today_eastern() + timedelta(days=1)).isoformat(), "steps": 100},
        {"day": "2026-10-01", "steps": -1},
        {"day": "2026-10-01", "steps": 100_001},
    ],
)
def test_rejects_bad_entries(client, joined, entry):
    _, member = joined
    assert client.post("/steps", json={"member_id": member["id"], "entries": [entry]}).status_code == 422


def test_unknown_member_and_family(client):
    assert client.post("/steps", json={"member_id": 999, "entries": [{"day": "2026-10-01", "steps": 1}]}).status_code == 404
    assert client.get("/families/999/leaderboards/weekly").status_code == 404


def test_leaderboards(client, joined):
    family, member = joined
    client.post("/steps", json={"member_id": member["id"], "entries": [{"day": today_eastern().isoformat(), "steps": 12_345}]})
    weekly = client.get(f"/families/{family['id']}/leaderboards/weekly").json()
    assert weekly["kind"] == "weekly"
    assert weekly["standings"][0] | {"prev_rank": None, "step_change": None} == {
        "member_id": member["id"],
        "name": "Chris",
        "steps": 12_345,
        "rank": 1,
        "medal": "🥇",
        "prev_rank": None,
        "step_change": None,
    }
    alltime = client.get(f"/families/{family['id']}/leaderboards/all-time", params={"as_of": today_eastern().isoformat()}).json()
    assert alltime["standings"][0]["steps"] == 12_345


def test_digest_without_webhook_is_saved(client, joined):
    family, _ = joined
    message = client.post(f"/families/{family['id']}/digests", json={"kind": "monthly"}).json()
    assert message["discord_status"] == "not_configured"
    assert message["text"].startswith("🏅 All-time Steps")
    assert client.get(f"/families/{family['id']}/messages").json() == [message]


def test_post_to_discord(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, json=json)
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(digests.httpx, "post", fake_post)
    assert digests.post_to_discord("https://discord.test/hook", "hi") == "sent"
    assert sent == {"url": "https://discord.test/hook", "json": {"content": "hi"}}


def test_post_to_discord_failure(monkeypatch):
    def failing_post(url, json, timeout):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(digests.httpx, "post", failing_post)
    assert digests.post_to_discord("https://discord.test/hook", "hi") == "failed"
    assert digests.post_to_discord(None, "hi") == "not_configured"
