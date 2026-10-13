from datetime import date

from stepboard import db
from stepboard.reports import alltime_board, weekly_board
from stepboard.seed import seed_demo_family

TODAY = date(2026, 10, 14)  # a Wednesday


def test_seed_fills_both_boards(session):
    family = seed_demo_family(session, TODAY)
    assert family.start_date == date(2026, 9, 14)  # Monday, 4 weeks before this week

    weekly = weekly_board(session, family, TODAY)
    assert weekly.has_comparison
    assert [s.medal for s in weekly.standings[:3]] == ["🥇", "🥈", "🥉"]
    assert all(s.steps > 0 for s in alltime_board(session, family, TODAY).standings)


def test_seed_fills_this_week_even_on_a_monday(session):
    monday = date(2026, 10, 12)
    family = seed_demo_family(session, monday)
    assert all(s.steps > 0 for s in weekly_board(session, family, monday).standings)
    assert session.get(db.StepEntry, (1, monday)).source == "seed"


def test_seed_runs_once(session):
    assert seed_demo_family(session, TODAY) is not None
    assert seed_demo_family(session, TODAY) is None
