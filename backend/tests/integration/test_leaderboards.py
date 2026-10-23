"""The leaderboard endpoints over HTTP, including the demo family's boards."""

from datetime import date, timedelta

import pytest

from leaderboard.dates import today_eastern
from leaderboard.models import Family, Member, StepEntry
from leaderboard.seed import seed_demo_family

pytestmark = pytest.mark.django_db

SEEDED_ON = date(2026, 10, 14)  # a Wednesday
LAST_SUNDAY = date(2026, 10, 11)

STANDING_FIELDS = {"member_id", "name", "steps", "rank", "medal", "prev_rank", "step_change"}
BOARD_FIELDS = {"kind", "title", "start", "end", "has_comparison", "standings", "callouts"}


@pytest.fixture
def demo():
    return seed_demo_family(SEEDED_ON)


def board(client, family_id, which, **params):
    return client.get(f"/families/{family_id}/leaderboards/{which}", params)


def test_response_matches_the_contract(client, demo):
    for which, kind in [("weekly", "weekly"), ("all-time", "all_time")]:
        body = board(client, demo.id, which, as_of=LAST_SUNDAY.isoformat()).json()
        assert set(body) == BOARD_FIELDS
        assert body["kind"] == kind
        assert all(set(s) == STANDING_FIELDS for s in body["standings"])
        assert all(set(c) == {"kind", "text"} for c in body["callouts"])


def test_demo_weekly_board_has_medals_rank_changes_and_callouts(client, demo):
    """Finishes task 5's check: the seeded family's boards are worth looking at."""
    body = board(client, demo.id, "weekly", as_of=LAST_SUNDAY.isoformat()).json()
    standings = body["standings"]
    assert body["title"] == "🏆 Weekly Steps — Oct 5–11"
    assert body["has_comparison"]
    assert [s["medal"] for s in standings] == ["🥇", "🥈", "🥉", None]
    assert any(s["prev_rank"] != s["rank"] for s in standings)
    assert [c["kind"] for c in body["callouts"]] == ["best_single_day", "most_improved"]


def test_demo_week_so_far_and_all_time(client, demo):
    so_far = board(client, demo.id, "weekly", as_of=SEEDED_ON.isoformat()).json()
    assert so_far["title"] == "📊 Week So Far — Oct 12–14"
    assert all(s["steps"] > 0 for s in so_far["standings"])

    all_time = board(client, demo.id, "all-time", as_of=SEEDED_ON.isoformat()).json()
    assert all_time["has_comparison"]  # compared with the end of September
    assert [s["medal"] for s in all_time["standings"][:3]] == ["🥇", "🥈", "🥉"]
    assert all_time["callouts"][0]["text"].startswith("🔥 Best day ever:")


def test_as_of_defaults_to_today_eastern(client, demo):
    for which in ["weekly", "all-time"]:
        assert board(client, demo.id, which).json()["end"] == today_eastern().isoformat()


def test_unknown_family(client):
    for which in ["weekly", "all-time"]:
        response = board(client, 999, which, as_of="soon")  # 404 comes before the date check
        assert (response.status_code, response.json()) == (404, {"detail": "Family not found"})


def test_bad_as_of(client, demo):
    response = board(client, demo.id, "weekly", as_of="last sunday")
    assert response.status_code == 422
    assert response.json() == {"detail": "as_of: Date has wrong format. Use one of these formats instead: YYYY-MM-DD."}


def test_get_only(client, demo):
    assert client.post(f"/families/{demo.id}/leaderboards/weekly").status_code == 405


@pytest.mark.parametrize("which", ["weekly", "all-time"])
def test_query_count_does_not_grow_with_the_family(client, demo, django_assert_num_queries, which):
    """One query for the family, then a fixed four for the board, however many members or days."""
    with django_assert_num_queries(5):
        board(client, demo.id, which, as_of=SEEDED_ON.isoformat())

    for n in range(10):
        member = Member.objects.create(family=demo, name=f"Cousin {n}")
        StepEntry.objects.bulk_create(
            StepEntry(member=member, day=SEEDED_ON - timedelta(days=d), steps=5_000) for d in range(14)
        )
    with django_assert_num_queries(5):
        response = board(client, demo.id, which, as_of=SEEDED_ON.isoformat())
    assert len(response.json()["standings"]) == 14


def test_other_families_do_not_appear(client, demo):
    other = Family.objects.create(name="Neighbors", start_date=date(2026, 9, 1), invite_code="OTHER1")
    stranger = Member.objects.create(family=other, name="Stranger")
    StepEntry.objects.create(member=stranger, day=SEEDED_ON, steps=99_999)
    names = {s["name"] for s in board(client, demo.id, "weekly", as_of=SEEDED_ON.isoformat()).json()["standings"]}
    assert names == {"Dad", "Mom", "Alex", "Sam"}
