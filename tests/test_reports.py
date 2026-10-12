from datetime import date, timedelta

import pytest

from stepboard.bot import parse_day
from stepboard.db import Database
from stepboard.reports import alltime_report, weekly_report

LAUNCH = date(2026, 9, 28)  # a Monday


@pytest.fixture
def db():
    database = Database(":memory:")
    database.upsert_member(1, "Dad")
    database.upsert_member(2, "Mom")
    yield database
    database.close()


def log_week(db, member_id, monday, steps_per_day):
    for offset, steps in enumerate(steps_per_day):
        db.record_steps(member_id, monday + timedelta(days=offset), steps, "manual")


def test_later_value_replaces_earlier(db):
    db.record_steps(1, LAUNCH, 5_000, "manual")
    db.record_steps(1, LAUNCH, 7_500, "fitbit")
    assert db.totals(LAUNCH, LAUNCH) == {1: 7_500}


def test_first_week_has_no_movement(db):
    log_week(db, 1, LAUNCH, [10_000] * 7)
    log_week(db, 2, LAUNCH, [12_000] * 7)
    text = weekly_report(db, date(2026, 10, 4), LAUNCH)
    assert text.splitlines()[:3] == [
        "🏆 Weekly Steps — Sep 28–Oct 4",
        "🥇 Mom — 84,000",
        "🥈 Dad — 70,000",
    ]
    assert "Most improved" not in text


def test_second_week_compares_with_first(db):
    week2 = LAUNCH + timedelta(days=7)
    log_week(db, 1, LAUNCH, [10_000] * 7)
    log_week(db, 2, LAUNCH, [12_000] * 7)
    log_week(db, 1, week2, [13_000] * 7)
    log_week(db, 2, week2, [11_000] * 6 + [20_000])
    text = weekly_report(db, date(2026, 10, 11), LAUNCH)
    assert "🥇 Dad — 91,000 (▲ 1, +21,000 steps)" in text
    assert "🥈 Mom — 86,000 (▼ 1, +2,000 steps)" in text
    assert "🔥 Best single day: Mom, 20,000 on Sunday" in text
    assert "🚀 Most improved: Dad, +21,000 from last week" in text


def test_midweek_counts_monday_to_wednesday(db):
    week2 = LAUNCH + timedelta(days=7)
    log_week(db, 1, week2, [1_000] * 7)
    text = weekly_report(db, week2 + timedelta(days=2), LAUNCH)
    assert text.splitlines()[0] == "📊 Week So Far — Oct 5–7"
    assert "Dad — 3,000" in text


def test_steps_before_launch_do_not_count(db):
    db.record_steps(1, LAUNCH - timedelta(days=1), 50_000, "manual")
    db.record_steps(1, LAUNCH, 1_000, "manual")
    assert "🥇 Dad — 1,000" in alltime_report(db, LAUNCH, LAUNCH)


def test_alltime_compares_with_end_of_previous_month(db):
    log_week(db, 1, LAUNCH, [10_000] * 7)  # Sep 28 – Oct 4
    text = alltime_report(db, date(2026, 10, 31), LAUNCH)
    assert text.splitlines()[0] == "🏅 All-time Steps — since Sep 28, 2026"
    assert "🥇 Dad — 70,000 (—, +40,000 steps)" in text


def test_parse_day():
    today = date(2026, 10, 11)
    assert parse_day(None, today) == today
    assert parse_day("Yesterday", today) == date(2026, 10, 10)
    assert parse_day("2026-10-01", today) == date(2026, 10, 1)
    with pytest.raises(ValueError):
        parse_day("last tuesday", today)
