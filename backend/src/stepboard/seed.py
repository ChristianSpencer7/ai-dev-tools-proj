"""Creates the demo family with about 4 weeks of history plus part of today, so the boards are full on first load.

Run with `python -m stepboard.seed`. Safe to run again: it does nothing if the demo family exists.
"""

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from stepboard import db
from stepboard.config import Settings, today_eastern
from stepboard.leaderboard import week_start

DEMO_INVITE_CODE = "DEMO"
WEEKS_OF_HISTORY = 4

# name: (typical daily steps, change per week). Different trends make ranks move week to week.
DEMO_MEMBERS = {
    "Dad": (11_500, 300),
    "Mom": (12_000, -400),
    "Alex": (8_500, 600),
    "Sam": (7_000, 1_100),
}


def seed_demo_family(session: Session, today: date, rng: random.Random | None = None) -> db.Family | None:
    """Returns the new family, or None if it was already there."""
    if session.scalar(select(db.Family).where(db.Family.invite_code == DEMO_INVITE_CODE)):
        return None
    rng = rng or random.Random(42)
    start = week_start(today) - timedelta(weeks=WEEKS_OF_HISTORY)
    family = db.Family(name="Demo Family", start_date=start, invite_code=DEMO_INVITE_CODE)
    session.add(family)
    session.flush()

    for name, (typical, weekly_change) in DEMO_MEMBERS.items():
        member = db.Member(family_id=family.id, name=name)
        session.add(member)
        session.flush()
        day = start
        while day <= today:
            weeks_in = (day - start).days // 7
            mean = typical + weekly_change * weeks_in + (2_000 if day.weekday() >= 5 else 0)
            if day == today:
                mean *= 0.4  # the day is still going, so even on a Monday the week isn't empty
            steps = max(0, int(rng.gauss(mean, mean / 4)))
            db.record_steps(session, member.id, day, steps, "seed")
            day += timedelta(days=1)

    session.commit()
    return family


def main() -> None:
    settings = Settings.from_env()
    sessions = sessionmaker(db.make_engine(settings.database_url), expire_on_commit=False)
    with sessions() as session:
        family = seed_demo_family(session, today_eastern())
    if family:
        print(f"Seeded '{family.name}' (invite code {DEMO_INVITE_CODE}) starting {family.start_date}")
    else:
        print("Demo family already exists; nothing to do")


if __name__ == "__main__":
    main()
