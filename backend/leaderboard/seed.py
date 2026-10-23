"""The demo family: about 4 weeks of history plus part of today, so the boards are full on first load.

Safe to run again: it does nothing if the demo family already exists.
"""

import random
from datetime import date, timedelta

from django.db import transaction

from leaderboard.models import Family, Member, StepEntry
from leaderboard.ranking import week_start
from leaderboard.serializers import MAX_DAILY_STEPS

DEMO_FAMILY_NAME = "Demo Family"
DEMO_INVITE_CODE = "DEMO"  # can't clash with a generated code: those are 6 characters and never contain O
WEEKS_OF_HISTORY = 4
RANDOM_SEED = 42  # the same date always gives the same demo

# name: (typical daily steps, change per week). Different trends make ranks move week to week.
DEMO_MEMBERS = {
    "Dad": (11_500, 300),
    "Mom": (12_000, -400),
    "Alex": (8_500, 600),
    "Sam": (7_000, 1_100),
}
WEEKEND_BONUS = 2_000
PARTIAL_TODAY = 0.4  # the day is still going, so even on a Monday the week isn't empty


def seed_demo_family(today: date, rng: random.Random | None = None) -> Family | None:
    """Creates the demo family with daily steps from 4 weeks before this week through today.

    Returns the new family, or None if it was already there.
    """
    if Family.objects.filter(invite_code=DEMO_INVITE_CODE).exists():
        return None
    rng = rng or random.Random(RANDOM_SEED)
    start = week_start(today) - timedelta(weeks=WEEKS_OF_HISTORY)

    with transaction.atomic():
        family = Family.objects.create(name=DEMO_FAMILY_NAME, start_date=start, invite_code=DEMO_INVITE_CODE)
        entries = []
        for name, (typical, weekly_change) in DEMO_MEMBERS.items():
            member = Member.objects.create(family=family, name=name)
            for offset in range((today - start).days + 1):
                day = start + timedelta(days=offset)
                mean = typical + weekly_change * (offset // 7) + (WEEKEND_BONUS if day.weekday() >= 5 else 0)
                if day == today:
                    mean *= PARTIAL_TODAY
                steps = min(MAX_DAILY_STEPS, max(0, round(rng.gauss(mean, mean / 4))))
                entries.append(StepEntry(member=member, day=day, steps=steps, source=StepEntry.Source.SEED))
        StepEntry.objects.bulk_create(entries)
    return family
