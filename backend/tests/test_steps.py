"""Logging and importing daily step totals, and reading a member's history, through the HTTP API."""

from datetime import date, timedelta
from unittest import mock

import pytest
from django.db import DatabaseError

from leaderboard.models import Family, Member, StepEntry

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 14)  # a Wednesday; "today" is pinned so future-day checks don't depend on the clock


def day(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch):
    monkeypatch.setattr("leaderboard.serializers.today_eastern", lambda: TODAY)


@pytest.fixture
def member():
    family = Family.objects.create(name="Spencers", start_date=date(2026, 9, 1), invite_code="TEST01")
    return Member.objects.create(family=family, name="Chris")


def log(client, member_id, entries, source=None):
    body = {"member_id": member_id, "entries": entries}
    if source:
        body["source"] = source
    return client.post("/steps", body, content_type="application/json")


# --- POST /steps ---------------------------------------------------------------------------------


def test_logging_a_day_again_replaces_it(client, member):
    log(client, member.id, [{"day": day(0), "steps": 4_000}])
    response = log(client, member.id, [{"day": day(0), "steps": 9_000}], source="import")

    assert response.status_code == 200
    assert response.json() == [{"member_id": member.id, "day": day(0), "steps": 9_000, "source": "import"}]
    entry = StepEntry.objects.get(member=member)  # still exactly one row
    assert (entry.steps, entry.source) == (9_000, "import")


def test_import_several_days(client, member):
    entries = [{"day": day(n), "steps": 5_000 + n} for n in range(3)]
    response = log(client, member.id, entries, source="shortcut")

    assert response.status_code == 200
    assert [(e["day"], e["steps"], e["source"]) for e in response.json()] == [
        (day(0), 5_000, "shortcut"),
        (day(1), 5_001, "shortcut"),
        (day(2), 5_002, "shortcut"),
    ]
    assert StepEntry.objects.filter(member=member).count() == 3


def test_import_mixes_new_and_existing_days(client, member):
    log(client, member.id, [{"day": day(1), "steps": 1_000}])
    log(client, member.id, [{"day": day(1), "steps": 2_000}, {"day": day(0), "steps": 3_000}])
    assert dict(StepEntry.objects.values_list("day", "steps")) == {TODAY - timedelta(days=1): 2_000, TODAY: 3_000}


def test_source_defaults_to_manual(client, member):
    assert log(client, member.id, [{"day": day(0), "steps": 1}]).json()[0]["source"] == "manual"


def test_limits_are_allowed(client, member):
    """0 and 100,000 steps, today itself, and a full 366-day import are all fine."""
    assert log(client, member.id, [{"day": day(0), "steps": 0}, {"day": day(1), "steps": 100_000}]).status_code == 200
    year = [{"day": day(n), "steps": 1} for n in range(366)]
    assert log(client, member.id, year).status_code == 200
    assert StepEntry.objects.count() == 366


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"entries": [{"day": day(-1), "steps": 1}]}, "entries: These days haven't happened yet: 2026-10-15."),
        ({"entries": [{"day": day(0), "steps": -1}]}, "entries.0.steps: Steps must be 0 or more."),
        ({"entries": [{"day": day(1), "steps": 1}, {"day": day(0), "steps": 100_001}]}, "entries.1.steps: Steps must be 100,000 or fewer."),
        ({"entries": []}, "entries: This list may not be empty."),
        ({"entries": [{"day": day(n), "steps": 1} for n in range(367)]}, "entries: Ensure this field has no more than 366 elements."),
        ({"source": "strava", "entries": [{"day": day(0), "steps": 1}]}, 'source: "strava" is not a valid choice.'),
        ({"entries": [{"day": day(0)}]}, "entries.0.steps: This field is required."),
        ({"entries": [{"steps": 1}]}, "entries.0.day: This field is required."),
        ({"entries": [{"day": "Oct 14", "steps": 1}]}, "entries.0.day: Date has wrong format. Use one of these formats instead: YYYY-MM-DD."),
        ({"entries": [{"day": day(0), "steps": 1}, {"day": day(0), "steps": 2}]}, "entries: Each day can appear only once: 2026-10-14."),
    ],
    ids=["future day", "negative", "over 100,000", "no entries", "367 entries", "unknown source",
         "missing steps", "missing day", "bad date", "same day twice"],
)
def test_rejections_are_422_and_save_nothing(client, member, body, detail):
    response = client.post("/steps", {"member_id": member.id, **body}, content_type="application/json")
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert not StepEntry.objects.exists()


def test_missing_member_id(client):
    response = client.post("/steps", {"entries": [{"day": day(0), "steps": 1}]}, content_type="application/json")
    assert (response.status_code, response.json()) == (422, {"detail": "member_id: This field is required."})


def test_one_bad_entry_saves_none_of_the_batch(client, member):
    log(client, member.id, [{"day": day(0), "steps": 4_000}])
    response = log(client, member.id, [{"day": day(0), "steps": 9_000}, {"day": day(1), "steps": 100_001}])
    assert response.status_code == 422
    assert list(StepEntry.objects.values_list("day", "steps")) == [(TODAY, 4_000)]  # the good entry wasn't applied


def test_a_failed_save_rolls_back_the_whole_batch(client, member):
    real_update_or_create = StepEntry.objects.update_or_create
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise DatabaseError("simulated failure")
        return real_update_or_create(*args, **kwargs)

    with mock.patch.object(StepEntry.objects, "update_or_create", side_effect=fail_on_second):
        with pytest.raises(DatabaseError):
            log(client, member.id, [{"day": day(0), "steps": 1}, {"day": day(1), "steps": 2}])
    assert not StepEntry.objects.exists()


def test_unknown_member(client):
    response = log(client, 999, [{"day": day(0), "steps": 1}])
    assert (response.status_code, response.json()) == (404, {"detail": "Member not found"})


def test_post_only(client):
    assert client.get("/steps").status_code == 405


# --- GET /members/{id}/steps ---------------------------------------------------------------------


@pytest.fixture
def history(member):
    """20 days of entries for the member (steps = 1,000 + days ago), plus another member's entry today."""
    for n in range(20):
        StepEntry.objects.create(member=member, day=TODAY - timedelta(days=n), steps=1_000 + n)
    other = Member.objects.create(family=member.family, name="Mom")
    StepEntry.objects.create(member=other, day=TODAY, steps=99_999)
    return member


def days_in(response) -> list[str]:
    return [entry["day"] for entry in response.json()]


def test_history_defaults_to_the_last_14_days_newest_first(client, history):
    response = client.get(f"/members/{history.id}/steps")
    assert response.status_code == 200
    assert days_in(response) == [day(n) for n in range(14)]
    assert {entry["member_id"] for entry in response.json()} == {history.id}  # Mom's entry is left out


def test_history_from_and_to(client, history):
    response = client.get(f"/members/{history.id}/steps", {"from": day(5), "to": day(3)})
    assert days_in(response) == [day(3), day(4), day(5)]


def test_history_only_to_gives_the_14_days_before_it(client, history):
    assert days_in(client.get(f"/members/{history.id}/steps", {"to": day(6)})) == [day(n) for n in range(6, 20)]


def test_history_only_from_runs_through_today(client, history):
    assert days_in(client.get(f"/members/{history.id}/steps", {"from": day(2)})) == [day(0), day(1), day(2)]


def test_history_with_no_entries(client, member):
    assert client.get(f"/members/{member.id}/steps").json() == []


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"from": day(1), "to": day(5)}, "from must be on or before to."),
        ({"to": "yesterday"}, "to: Date has wrong format. Use one of these formats instead: YYYY-MM-DD."),
    ],
)
def test_history_bad_dates_are_422(client, member, params, detail):
    response = client.get(f"/members/{member.id}/steps", params)
    assert (response.status_code, response.json()) == (422, {"detail": detail})


def test_history_unknown_member(client):
    response = client.get("/members/999/steps")
    assert (response.status_code, response.json()) == (404, {"detail": "Member not found"})
