"""Database reads for the leaderboards. Each function is one query; the ranking rules live in ranking.py."""

from datetime import date

from django.db.models import Sum

from leaderboard.models import Family, StepEntry
from leaderboard.ranking import DayRecord


def family_entries(family: Family, start: date, end: date):
    """The family's step entries from start through end, inclusive. Empty when start is after end."""
    return StepEntry.objects.filter(member__family=family, day__range=(start, end))


def totals(family: Family, start: date, end: date) -> dict[int, int]:
    """Total steps per member from start through end. Members with no entries are left out."""
    rows = family_entries(family, start, end).values("member_id").annotate(total=Sum("steps")).order_by()
    return {row["member_id"]: row["total"] for row in rows}


def daily(family: Family, start: date, end: date) -> list[DayRecord]:
    """Each day's entry from start through end, oldest first, for the best-single-day callout."""
    rows = family_entries(family, start, end).order_by("day", "member_id").values_list("member_id", "day", "steps")
    return [DayRecord(member_id, day, steps) for member_id, day, steps in rows]


def member_names(family: Family) -> dict[int, str]:
    """Every member of the family, including those with no steps yet, so they still appear on the boards."""
    return dict(family.members.values_list("id", "name"))
