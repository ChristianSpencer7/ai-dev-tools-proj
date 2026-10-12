"""Leaderboard math and message formatting. Pure functions, no I/O."""

from dataclasses import dataclass
from datetime import date, timedelta

MEDALS = ("🥇", "🥈", "🥉")


@dataclass(frozen=True)
class DayRecord:
    member_id: int
    day: date
    steps: int


@dataclass(frozen=True)
class Standing:
    member_id: int
    name: str
    steps: int
    rank: int
    prev_rank: int | None = None
    prev_steps: int | None = None

    @property
    def step_change(self) -> int | None:
        return None if self.prev_steps is None else self.steps - self.prev_steps


def week_start(day: date) -> date:
    """Monday of the week containing day."""
    return day - timedelta(days=day.weekday())


def format_range(start: date, end: date) -> str:
    """'Oct 5–11', or 'Sep 29–Oct 5' across months."""
    if (start.year, start.month) == (end.year, end.month):
        return f"{start:%b} {start.day}–{end.day}"
    return f"{start:%b} {start.day}–{end:%b} {end.day}"


def assign_ranks(totals: dict[int, int]) -> dict[int, int]:
    """Rank by steps, most first. Ties share a rank: 1, 1, 3."""
    ranks: dict[int, int] = {}
    last_steps, last_rank = None, 0
    ordered = sorted(totals.items(), key=lambda item: -item[1])
    for position, (member_id, steps) in enumerate(ordered, start=1):
        if steps != last_steps:
            last_steps, last_rank = steps, position
        ranks[member_id] = last_rank
    return ranks


def build_standings(
    current: dict[int, int],
    previous: dict[int, int] | None,
    names: dict[int, str],
) -> list[Standing]:
    """Rank every member for the current period, with movement against the previous one.

    previous is None when there is no previous period (before launch day). A member
    missing from previous shows as new.
    """
    totals = {member_id: current.get(member_id, 0) for member_id in names}
    ranks = assign_ranks(totals)
    prev_ranks = assign_ranks(previous) if previous else {}
    standings = [
        Standing(
            member_id=member_id,
            name=names[member_id],
            steps=steps,
            rank=ranks[member_id],
            prev_rank=prev_ranks.get(member_id),
            prev_steps=previous.get(member_id) if previous else None,
        )
        for member_id, steps in totals.items()
    ]
    return sorted(standings, key=lambda s: (s.rank, s.name.lower()))


def best_single_day(records: list[DayRecord]) -> DayRecord | None:
    """Highest single-day count; the earliest day wins a tie."""
    best = None
    for record in sorted(records, key=lambda r: r.day):
        if record.steps > 0 and (best is None or record.steps > best.steps):
            best = record
    return best


def most_improved(standings: list[Standing]) -> Standing | None:
    """Largest step gain over the previous period, if anyone gained."""
    gains = [s for s in standings if s.step_change is not None and s.step_change > 0]
    return max(gains, key=lambda s: s.step_change, default=None)


def _change_text(standing: Standing) -> str:
    if standing.prev_rank is None:
        return " (new)"
    move = standing.prev_rank - standing.rank
    arrow = f"▲ {move}" if move > 0 else f"▼ {-move}" if move < 0 else "—"
    return f" ({arrow}, {standing.step_change:+,} steps)"


def format_board(
    title: str,
    standings: list[Standing],
    *,
    show_change: bool,
    callouts: list[str] = (),
) -> str:
    lines = [title]
    if not standings:
        lines.append("No one has joined yet.")
    for s in standings:
        label = MEDALS[s.rank - 1] if s.rank <= len(MEDALS) else f"{s.rank}."
        change = _change_text(s) if show_change else ""
        lines.append(f"{label} {s.name} — {s.steps:,}{change}")
    if callouts:
        lines.append("")
        lines.extend(callouts)
    return "\n".join(lines)
