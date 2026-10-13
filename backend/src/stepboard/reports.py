"""Builds leaderboards from the database. The same Board feeds the API and the digest text."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from stepboard import db
from stepboard.leaderboard import (
    Standing,
    best_single_day,
    build_standings,
    format_board,
    format_range,
    most_improved,
    week_start,
)

WEEK = timedelta(days=7)


@dataclass(frozen=True)
class Callout:
    kind: Literal["best_single_day", "most_improved"]
    text: str


@dataclass(frozen=True)
class Board:
    kind: Literal["weekly", "all_time"]
    title: str
    start: date
    end: date
    has_comparison: bool
    standings: list[Standing]
    callouts: list[Callout] = field(default_factory=list)

    def text(self) -> str:
        return format_board(
            self.title,
            self.standings,
            show_change=self.has_comparison,
            callouts=[c.text for c in self.callouts],
        )


def weekly_board(session: Session, family: db.Family, end_day: date) -> Board:
    """Standings from Monday through end_day, compared with the same days last week.

    With end_day on a Sunday this is the final weekly board; earlier in the week it
    is the standings so far.
    """
    start = week_start(end_day)
    if end_day.weekday() == 6:
        title = f"🏆 Weekly Steps — {format_range(start, end_day)}"
    else:
        title = f"📊 Week So Far — {format_range(start, end_day)}"

    counted_from = max(start, family.start_date)
    current = db.totals(session, family.id, counted_from, end_day)
    prev_end = end_day - WEEK
    previous = (
        db.totals(session, family.id, max(start - WEEK, family.start_date), prev_end)
        if prev_end >= family.start_date
        else None
    )
    names = db.member_names(session, family.id)
    standings = build_standings(current, previous, names)

    callouts = []
    if best := best_single_day(db.daily(session, family.id, counted_from, end_day)):
        callouts.append(
            Callout(
                "best_single_day",
                f"🔥 Best single day: {names[best.member_id]}, {best.steps:,} on {best.day:%A}",
            )
        )
    if previous is not None and (improved := most_improved(standings)):
        callouts.append(
            Callout(
                "most_improved",
                f"🚀 Most improved: {improved.name}, {improved.step_change:+,} from last week",
            )
        )

    return Board("weekly", title, start, end_day, previous is not None, standings, callouts)


def alltime_board(session: Session, family: db.Family, as_of: date) -> Board:
    """Totals since the family's start date, compared with the end of the previous month."""
    start = family.start_date
    title = f"🏅 All-time Steps — since {start:%b} {start.day}, {start.year}"
    current = db.totals(session, family.id, start, as_of)
    prev_end = as_of.replace(day=1) - timedelta(days=1)
    previous = db.totals(session, family.id, start, prev_end) if prev_end >= start else None
    names = db.member_names(session, family.id)
    standings = build_standings(current, previous, names)

    callouts = []
    if best := best_single_day(db.daily(session, family.id, start, as_of)):
        callouts.append(
            Callout(
                "best_single_day",
                f"🔥 Best day ever: {names[best.member_id]}, {best.steps:,} on "
                f"{best.day:%b} {best.day.day}, {best.day.year}",
            )
        )

    return Board("all_time", title, start, as_of, previous is not None, standings, callouts)
