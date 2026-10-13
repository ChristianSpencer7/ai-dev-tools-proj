from datetime import date, timedelta

from conftest import START

from stepboard import db
from stepboard.reports import alltime_board, weekly_board


def log_week(session, member_id, monday, steps_per_day):
    for offset, steps in enumerate(steps_per_day):
        db.record_steps(session, member_id, monday + timedelta(days=offset), steps, "manual")
    session.commit()


def test_later_value_replaces_earlier(session, family):
    db.record_steps(session, 1, START, 5_000, "manual")
    db.record_steps(session, 1, START, 7_500, "import")
    session.commit()
    assert db.totals(session, family.id, START, START) == {1: 7_500}


def test_first_week_has_no_movement(session, family):
    log_week(session, 1, START, [10_000] * 7)
    log_week(session, 2, START, [12_000] * 7)
    board = weekly_board(session, family, date(2026, 10, 4))
    assert not board.has_comparison
    assert board.text().splitlines()[:3] == [
        "🏆 Weekly Steps — Sep 28–Oct 4",
        "🥇 Mom — 84,000",
        "🥈 Dad — 70,000",
    ]
    assert [c.kind for c in board.callouts] == ["best_single_day"]


def test_second_week_compares_with_first(session, family):
    week2 = START + timedelta(days=7)
    log_week(session, 1, START, [10_000] * 7)
    log_week(session, 2, START, [12_000] * 7)
    log_week(session, 1, week2, [13_000] * 7)
    log_week(session, 2, week2, [11_000] * 6 + [20_000])
    text = weekly_board(session, family, date(2026, 10, 11)).text()
    assert "🥇 Dad — 91,000 (▲ 1, +21,000 steps)" in text
    assert "🥈 Mom — 86,000 (▼ 1, +2,000 steps)" in text
    assert "🔥 Best single day: Mom, 20,000 on Sunday" in text
    assert "🚀 Most improved: Dad, +21,000 from last week" in text


def test_week_so_far_counts_monday_through_as_of(session, family):
    week2 = START + timedelta(days=7)
    log_week(session, 1, week2, [1_000] * 7)
    board = weekly_board(session, family, week2 + timedelta(days=2))
    assert board.title == "📊 Week So Far — Oct 5–7"
    assert (board.standings[0].name, board.standings[0].steps) == ("Dad", 3_000)


def test_steps_before_start_date_do_not_count(session, family):
    db.record_steps(session, 1, START - timedelta(days=1), 50_000, "manual")
    db.record_steps(session, 1, START, 1_000, "manual")
    session.commit()
    assert "🥇 Dad — 1,000" in alltime_board(session, family, START).text()


def test_alltime_compares_with_end_of_previous_month(session, family):
    log_week(session, 1, START, [10_000] * 7)  # Sep 28 – Oct 4
    text = alltime_board(session, family, date(2026, 10, 31)).text()
    assert text.splitlines()[0] == "🏅 All-time Steps — since Sep 28, 2026"
    assert "🥇 Dad — 70,000 (—, +40,000 steps)" in text


def test_other_families_are_not_counted(session, family):
    other = db.Family(name="Other", start_date=START, invite_code="OTHER1")
    session.add(other)
    session.flush()
    session.add(db.Member(id=3, family_id=other.id, name="Stranger"))
    db.record_steps(session, 3, START, 99_000, "manual")
    session.commit()
    names = [s.name for s in alltime_board(session, family, START).standings]
    assert "Stranger" not in names
