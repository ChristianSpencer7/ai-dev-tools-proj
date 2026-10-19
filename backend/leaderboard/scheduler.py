"""The digest schedule: weekly on Mondays and monthly on the 1st, both at 8:00 AM Eastern."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.db import close_old_connections

from leaderboard.dates import today_eastern
from leaderboard.digests import send_scheduled_digests
from leaderboard.models import Message

log = logging.getLogger(__name__)

EASTERN = ZoneInfo(settings.TIME_ZONE)  # America/New_York
# If the scheduler was down at 8:00 (a restart, a sleeping laptop), still send when it's back within 6 hours.
MISFIRE_GRACE_SECONDS = 6 * 60 * 60

SCHEDULE = {
    # kind: when it runs. Each digest counts through yesterday: Sunday's week, or last month's final day.
    Message.Kind.WEEKLY: CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=EASTERN),
    Message.Kind.MONTHLY: CronTrigger(day=1, hour=8, minute=0, timezone=EASTERN),
}


def run_scheduled_digests(kind: str) -> None:
    """One scheduled run. Never raises, so a bad run doesn't stop the schedule."""
    # This process runs for days; drop database connections the server may have closed in the meantime.
    close_old_connections()
    try:
        as_of = today_eastern() - timedelta(days=1)
        run = send_scheduled_digests(kind, as_of)
        log.info(
            "%s digests as of %s: %d sent, %d skipped, %d failed",
            kind.capitalize(), as_of, len(run.sent), len(run.skipped), len(run.failed),
        )
    except Exception:
        log.exception("The scheduled %s digests failed", kind)
    finally:
        close_old_connections()


def build_scheduler(scheduler_class: type[BaseScheduler] = BlockingScheduler) -> BaseScheduler:
    # One job at a time: when the 1st is a Monday both run at 8:00, and on SQLite two writers at once fail.
    scheduler = scheduler_class(timezone=EASTERN, executors={"default": ThreadPoolExecutor(max_workers=1)})
    for kind, trigger in SCHEDULE.items():
        scheduler.add_job(
            run_scheduled_digests,
            trigger,
            args=[kind],
            id=f"{kind}-digests",
            name=f"{kind.capitalize()} digests",
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,  # several missed runs become one
            max_instances=1,
        )
    return scheduler


def next_runs(now: datetime | None = None) -> dict[str, datetime]:
    """When each digest runs next, in Eastern time."""
    now = now or datetime.now(EASTERN)
    return {kind: trigger.get_next_fire_time(None, now) for kind, trigger in SCHEDULE.items()}
