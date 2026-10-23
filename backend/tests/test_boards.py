"""Weekly and all-time boards. The first group is ported from the FastAPI version's test_reports.py."""

from datetime import date, timedelta

import pytest

from leaderboard.boards import alltime_board, weekly_board
from leaderboard.models import Family, Member, StepEntry

pytestmark = pytest.mark.django_db

START = date(2026, 9, 28)  # a Monday


@pytest.fixture
def family():
    """A family starting on START with Dad (id 1) and Mom (id 2)."""
    fam = Family.objects.create(name="Test", start_date=START, invite_code="TEST01")
    Member.objects.create(id=1, family=fam, name="Dad")
    Member.objects.create(id=2, family=fam, name="Mom")
    return fam


def log(member_id, day, steps):
    StepEntry.objects.create(member_id=member_id, day=day, steps=steps)


def log_week(member_id, monday, steps_per_day):
    for offset, steps in enumerate(steps_per_day):
        log(member_id, monday + timedelta(days=offset), steps)


# --- Ported from the FastAPI test_reports.py -------------------------------------------------------


def test_first_week_has_no_movement(family):
    log_week(1, START, [10_000] * 7)
    log_week(2, START, [12_000] * 7)
    board = weekly_board(family, date(2026, 10, 4))
    assert not board.has_comparison
    assert board.text().splitlines()[:3] == [
        "🏆 Weekly Steps — Sep 28–Oct 4",
        "🥇 Mom — 84,000",
        "🥈 Dad — 70,000",
    ]
    assert [c.kind for c in board.callouts] == ["best_single_day"]


def test_second_week_compares_with_first(family):
    week2 = START + timedelta(days=7)
    log_week(1, START, [10_000] * 7)
    log_week(2, START, [12_000] * 7)
    log_week(1, week2, [13_000] * 7)
    log_week(2, week2, [11_000] * 6 + [20_000])
    text = weekly_board(family, date(2026, 10, 11)).text()
    assert "🥇 Dad — 91,000 (▲ 1, +21,000 steps)" in text
    assert "🥈 Mom — 86,000 (▼ 1, +2,000 steps)" in text
    assert "🔥 Best single day: Mom, 20,000 on Sunday" in text
    assert "🚀 Most improved: Dad, +21,000 from last week" in text


def test_week_so_far_counts_monday_through_as_of(family):
    week2 = START + timedelta(days=7)
    log_week(1, week2, [1_000] * 7)
    board = weekly_board(family, week2 + timedelta(days=2))
    assert board.title == "📊 Week So Far — Oct 5–7"
    assert (board.standings[0].name, board.standings[0].steps) == ("Dad", 3_000)


def test_week_so_far_compares_with_the_same_days_last_week(family):
    """Wednesday's board compares Mon–Wed with last Mon–Wed, not with all of last week."""
    week2 = START + timedelta(days=7)
    log_week(1, START, [1_000] * 7)
    log_week(1, week2, [1_000] * 3)
    dad = weekly_board(family, week2 + timedelta(days=2)).standings[0]
    assert (dad.steps, dad.step_change) == (3_000, 0)


def test_steps_before_start_date_do_not_count(family):
    log(1, START - timedelta(days=1), 50_000)
    log(1, START, 1_000)
    assert "🥇 Dad — 1,000" in alltime_board(family, START).text()
    assert weekly_board(family, START).standings[0].steps == 1_000


def test_alltime_compares_with_end_of_previous_month(family):
    log_week(1, START, [10_000] * 7)  # Sep 28 – Oct 4
    text = alltime_board(family, date(2026, 10, 31)).text()
    assert text.splitlines()[0] == "🏅 All-time Steps — since Sep 28, 2026"
    assert "🥇 Dad — 70,000 (—, +40,000 steps)" in text


def test_other_families_are_not_counted(family):
    other = Family.objects.create(name="Other", start_date=START, invite_code="OTHER1")
    Member.objects.create(id=3, family=other, name="Stranger")
    log(3, START, 99_000)
    names = [s.name for s in alltime_board(family, START).standings]
    assert "Stranger" not in names


# --- More board rules ------------------------------------------------------------------------------


def test_ties_share_a_rank_and_a_medal(family):
    Member.objects.create(id=3, family=family, name="Alex")
    log(1, START, 5_000)
    log(2, START, 5_000)
    log(3, START, 4_000)
    standings = weekly_board(family, START).standings
    assert [(s.name, s.rank, s.medal) for s in standings] == [("Dad", 1, "🥇"), ("Mom", 1, "🥇"), ("Alex", 3, "🥉")]


def test_members_with_no_steps_are_ranked_last_with_zero(family):
    log(1, START, 5_000)
    standings = weekly_board(family, START).standings
    assert [(s.name, s.steps, s.rank) for s in standings] == [("Dad", 5_000, 1), ("Mom", 0, 2)]


def test_a_member_with_no_steps_last_week_shows_as_new(family):
    week2 = START + timedelta(days=7)
    log_week(1, START, [10_000] * 7)
    log_week(1, week2, [10_000] * 7)
    log_week(2, week2, [12_000] * 7)
    board = weekly_board(family, week2 + timedelta(days=6))
    mom = next(s for s in board.standings if s.name == "Mom")
    assert (mom.prev_rank, mom.step_change) == (None, None)
    assert "🥇 Mom — 84,000 (new)" in board.text()


def test_no_most_improved_when_nobody_gained(family):
    week2 = START + timedelta(days=7)
    log_week(1, START, [10_000] * 7)
    log_week(1, week2, [9_000] * 7)
    kinds = [c.kind for c in weekly_board(family, week2 + timedelta(days=6)).callouts]
    assert kinds == ["best_single_day"]


def test_no_callouts_when_nobody_has_steps(family):
    board = weekly_board(family, START)
    assert board.callouts == []
    assert [s.steps for s in board.standings] == [0, 0]


def test_family_that_starts_midweek(family):
    family.start_date = date(2026, 9, 30)  # a Wednesday
    family.save()
    log(1, date(2026, 9, 29), 50_000)  # Tuesday, before the start
    log(1, date(2026, 9, 30), 1_000)
    board = weekly_board(family, date(2026, 10, 4))
    assert (board.start, board.end) == (START, date(2026, 10, 4))  # the board still covers Monday–Sunday
    assert board.standings[0].steps == 1_000
    assert not board.has_comparison


def test_alltime_in_the_first_month_has_no_comparison(family):
    log(1, START, 1_000)
    board = alltime_board(family, date(2026, 9, 30))
    assert not board.has_comparison
    assert board.text().splitlines()[1] == "🥇 Dad — 1,000"
    assert board.callouts[0].text == "🔥 Best day ever: Dad, 1,000 on Sep 28, 2026"
