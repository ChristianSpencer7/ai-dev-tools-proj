"""Builds leaderboard messages from the database."""

from datetime import date, timedelta

from stepboard.db import Database
from stepboard.leaderboard import (
    best_single_day,
    build_standings,
    format_board,
    format_range,
    most_improved,
    week_start,
)

WEEK = timedelta(days=7)


def weekly_report(db: Database, end_day: date, launch_day: date) -> str:
    """Standings from Monday through end_day, compared with the same days last week.

    With end_day on a Sunday this is the final weekly board; earlier in the week it
    is the standings so far (the Thursday post uses Monday–Wednesday).
    """
    start = week_start(end_day)
    if end_day.weekday() == 6:
        title = f"🏆 Weekly Steps — {format_range(start, end_day)}"
    else:
        title = f"📊 Week So Far — {format_range(start, end_day)}"

    counted_from = max(start, launch_day)
    current = db.totals(counted_from, end_day)
    prev_end = end_day - WEEK
    previous = db.totals(max(start - WEEK, launch_day), prev_end) if prev_end >= launch_day else None
    names = db.members()
    standings = build_standings(current, previous, names)

    callouts = []
    if best := best_single_day(db.daily(counted_from, end_day)):
        callouts.append(f"🔥 Best single day: {names[best.member_id]}, {best.steps:,} on {best.day:%A}")
    if previous is not None and (improved := most_improved(standings)):
        callouts.append(f"🚀 Most improved: {improved.name}, {improved.step_change:+,} from last week")

    return format_board(title, standings, show_change=previous is not None, callouts=callouts)


def alltime_report(db: Database, as_of: date, launch_day: date) -> str:
    """Totals since launch day, compared with the end of the previous month."""
    title = f"🏅 All-time Steps — since {launch_day:%b} {launch_day.day}, {launch_day.year}"
    current = db.totals(launch_day, as_of)
    prev_end = as_of.replace(day=1) - timedelta(days=1)
    previous = db.totals(launch_day, prev_end) if prev_end >= launch_day else None
    names = db.members()
    standings = build_standings(current, previous, names)

    callouts = []
    if best := best_single_day(db.daily(launch_day, as_of)):
        callouts.append(
            f"🔥 Best day ever: {names[best.member_id]}, {best.steps:,} on "
            f"{best.day:%b} {best.day.day}, {best.day.year}"
        )

    return format_board(title, standings, show_change=previous is not None, callouts=callouts)
