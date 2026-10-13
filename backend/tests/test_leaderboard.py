from datetime import date

from stepboard.leaderboard import (
    DayRecord,
    assign_ranks,
    best_single_day,
    build_standings,
    format_board,
    format_range,
    most_improved,
    week_start,
)

NAMES = {1: "Dad", 2: "Mom", 3: "Alex", 4: "Sam"}


def test_week_start_is_monday():
    assert week_start(date(2026, 10, 11)) == date(2026, 10, 5)  # Sunday
    assert week_start(date(2026, 10, 5)) == date(2026, 10, 5)  # Monday


def test_format_range():
    assert format_range(date(2026, 10, 5), date(2026, 10, 11)) == "Oct 5–11"
    assert format_range(date(2026, 9, 28), date(2026, 10, 4)) == "Sep 28–Oct 4"
    assert format_range(date(2026, 10, 12), date(2026, 10, 12)) == "Oct 12"


def test_ties_share_a_rank():
    assert assign_ranks({1: 500, 2: 500, 3: 100}) == {1: 1, 2: 1, 3: 3}


def test_standings_include_members_with_no_steps():
    standings = build_standings({1: 100}, None, NAMES)
    assert [(s.name, s.steps, s.rank) for s in standings] == [
        ("Dad", 100, 1),
        ("Alex", 0, 2),
        ("Mom", 0, 2),
        ("Sam", 0, 2),
    ]


def test_movement_against_previous_period():
    standings = build_standings({1: 300, 2: 200}, {1: 100, 2: 250}, {1: "Dad", 2: "Mom"})
    dad, mom = standings
    assert (dad.rank, dad.prev_rank, dad.step_change) == (1, 2, 200)
    assert (mom.rank, mom.prev_rank, mom.step_change) == (2, 1, -50)
    assert most_improved(standings) == dad


def test_best_single_day_prefers_earliest_on_tie():
    records = [
        DayRecord(2, date(2026, 10, 7), 18_000),
        DayRecord(1, date(2026, 10, 6), 18_000),
        DayRecord(3, date(2026, 10, 8), 9_000),
    ]
    assert best_single_day(records) == DayRecord(1, date(2026, 10, 6), 18_000)
    assert best_single_day([]) is None


def test_format_board():
    standings = build_standings(
        {1: 84_210, 2: 79_455, 3: 61_980, 4: 52_300},
        {1: 78_000, 2: 80_000, 3: 60_000},
        NAMES,
    )
    text = format_board("🏆 Weekly Steps — Oct 5–11", standings, show_change=True, callouts=["🔥 x"])
    assert text == "\n".join(
        [
            "🏆 Weekly Steps — Oct 5–11",
            "🥇 Dad — 84,210 (▲ 1, +6,210 steps)",
            "🥈 Mom — 79,455 (▼ 1, -545 steps)",
            "🥉 Alex — 61,980 (—, +1,980 steps)",
            "4. Sam — 52,300 (new)",
            "",
            "🔥 x",
        ]
    )
