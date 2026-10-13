"""Sends the scheduled digests through the API.

Weekly: Mondays at 8:00 AM Eastern, for the week that ended Sunday.
Monthly: the 1st at 8:00 AM Eastern, all-time totals through the last day of the month.

Run with `python -m stepboard.scheduler`. API_URL points at the backend.
"""

import logging
import os
from datetime import timedelta

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from stepboard.config import EASTERN, today_eastern

log = logging.getLogger(__name__)


def send_all(api_url: str, kind: str) -> None:
    as_of = today_eastern() - timedelta(days=1)
    with httpx.Client(base_url=api_url, timeout=30) as client:
        for family in client.get("/families").raise_for_status().json():
            response = client.post(f"/families/{family['id']}/digests", json={"kind": kind, "as_of": as_of.isoformat()})
            if response.is_success:
                log.info("Sent %s digest for %s", kind, family["name"])
            else:
                log.error("%s digest for %s failed: %s", kind, family["name"], response.text)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    scheduler = BlockingScheduler(timezone=EASTERN)
    scheduler.add_job(send_all, CronTrigger(day_of_week="mon", hour=8, timezone=EASTERN), args=[api_url, "weekly"])
    scheduler.add_job(send_all, CronTrigger(day=1, hour=8, timezone=EASTERN), args=[api_url, "monthly"])
    log.info("Scheduler started; API at %s", api_url)
    scheduler.start()


if __name__ == "__main__":
    main()
