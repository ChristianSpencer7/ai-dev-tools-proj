"""Builds the weekly and all-time leaderboards. The same Board feeds the API and the digest text."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from leaderboard import queries
from leaderboard.models import Family
from leaderboard.ranking import (
    Standing,
    best_single_day,
    build_standings,
    format_board,
    format_range,
    most_improved,
    week_start,
)

WEEK = timedelta(days=7)
SUNDAY = 6


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
    has_comparison: bool  # False when there's no earlier period to compare with
    standings: list[Standing]
    callouts: list[Callout] = field(default_factory=list)

    def text(self) -> str:
        """The board as a digest message (task 7)."""
        return format_board(
            self.title,
            self.standings,
            show_change=self.has_comparison,
            callouts=[c.text for c in self.callouts],
        )


def weekly_board(family: Family, as_of: date) -> Board:
    """Standings from Monday through as_of, compared with the same days last week.

    With as_of on a Sunday this is the final weekly board; earlier in the week it is the standings so far.
    Steps from before the family's start date never count.
    """
    start = week_start(as_of)
    if as_of.weekday() == SUNDAY:
        title = f"🏆 Weekly Steps — {format_range(start, as_of)}"
    else:
        title = f"📊 Week So Far — {format_range(start, as_of)}"

    counted_from = max(start, family.start_date)
    current = queries.totals(family, counted_from, as_of)
    prev_end = as_of - WEEK
    previous = (
        queries.totals(family, max(start - WEEK, family.start_date), prev_end)
        if prev_end >= family.start_date
        else None  # the family's first week: nothing to compare with
    )
    names = queries.member_names(family)
    standings = build_standings(current, previous, names)

    callouts = []
    if best := best_single_day(queries.daily(family, counted_from, as_of)):
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

    return Board("weekly", title, start, as_of, previous is not None, standings, callouts)


def alltime_board(family: Family, as_of: date) -> Board:
    """Totals since the family's start date, compared with the totals at the end of the previous month."""
    start = family.start_date
    title = f"🏅 All-time Steps — since {start:%b} {start.day}, {start.year}"
    current = queries.totals(family, start, as_of)
    prev_end = as_of.replace(day=1) - timedelta(days=1)
    previous = queries.totals(family, start, prev_end) if prev_end >= start else None
    names = queries.member_names(family)
    standings = build_standings(current, previous, names)

    callouts = []
    if best := best_single_day(queries.daily(family, start, as_of)):
        callouts.append(
            Callout(
                "best_single_day",
                f"🔥 Best day ever: {names[best.member_id]}, {best.steps:,} on "
                f"{best.day:%b} {best.day.day}, {best.day.year}",
            )
        )

    return Board("all_time", title, start, as_of, previous is not None, standings, callouts)
