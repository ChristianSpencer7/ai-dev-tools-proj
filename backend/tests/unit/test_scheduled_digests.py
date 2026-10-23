"""Scheduled digests: the send_digests command and the run_scheduler schedule."""

import logging
import threading
import time
from datetime import date, datetime, timedelta
from io import StringIO

import httpx
import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command
from django.core.management.base import CommandError

from leaderboard import digests, scheduler
from leaderboard.models import Family, Member, Message, StepEntry
from leaderboard.scheduler import EASTERN, MISFIRE_GRACE_SECONDS, build_scheduler, next_runs
from leaderboard.seed import seed_demo_family

MONDAY = date(2026, 10, 19)
SUNDAY = MONDAY - timedelta(days=1)


@pytest.fixture
def today(monkeypatch):
    """Pins "today" for send_digests and the scheduler. Call it with a date to change it."""
    def set_today(day: date):
        monkeypatch.setattr("leaderboard.management.commands.send_digests.today_eastern", lambda: day)
        monkeypatch.setattr("leaderboard.scheduler.today_eastern", lambda: day)

    set_today(MONDAY)
    return set_today


@pytest.fixture
def families(db):
    """The Demo Family plus two real families that started before MONDAY's week."""
    seed_demo_family(MONDAY)
    spencers = Family.objects.create(name="Spencers", start_date=date(2026, 10, 1), invite_code="SPEN01")
    chris = Member.objects.create(family=spencers, name="Chris")
    StepEntry.objects.create(member=chris, day=SUNDAY, steps=12_000)
    grandparents = Family.objects.create(name="Grandparents", start_date=date(2026, 10, 1), invite_code="GRAN01")
    return spencers, grandparents


def send_digests(*args) -> str:
    out = StringIO()
    call_command("send_digests", *args, stdout=out, stderr=out)
    return out.getvalue()


def messages() -> list[tuple]:
    return list(Message.objects.order_by("id").values_list("family__name", "kind", "as_of"))


# --- send_digests ---------------------------------------------------------------------------------


def test_sends_one_digest_per_family_counting_through_yesterday(today, families):
    """The backlog's done check: running it by hand adds one message per family."""
    output = send_digests("weekly")

    assert messages() == [("Spencers", "weekly", SUNDAY), ("Grandparents", "weekly", SUNDAY)]
    assert all(m.text.startswith("🏆 Weekly Steps — Oct 12–18") for m in Message.objects.all())  # the full week
    assert "Sent 2 weekly digests (as of 2026-10-18)." in output
    assert "Skipped: Demo Family (demo)." in output


def test_monthly_on_the_first_covers_the_month_that_ended(today, families):
    today(date(2026, 11, 1))
    send_digests("monthly")
    assert messages() == [("Spencers", "monthly", date(2026, 10, 31)), ("Grandparents", "monthly", date(2026, 10, 31))]
    assert Message.objects.first().text.startswith("🏅 All-time Steps")


def test_running_twice_sends_nothing_the_second_time(today, families):
    send_digests("weekly")
    output = send_digests("weekly")
    assert len(messages()) == 2
    assert "Sent 0 weekly digests" in output
    assert "Spencers (already sent)" in output and "Grandparents (already sent)" in output


def test_weekly_and_monthly_are_tracked_separately(today, families):
    send_digests("weekly")
    send_digests("monthly")
    assert len(messages()) == 4


def test_a_send_now_digest_does_not_block_the_scheduled_one(client, today, families):
    """On Monday morning "Send digest now" counts through Monday; the scheduled digest counts through Sunday."""
    spencers, _ = families
    client.post(f"/families/{spencers.id}/digests", {"kind": "weekly", "as_of": MONDAY.isoformat()}, content_type="application/json")
    send_digests("weekly")
    assert Message.objects.filter(family=spencers, kind="weekly").count() == 2


def test_include_demo(today, families):
    output = send_digests("weekly", "--include-demo")
    assert ("Demo Family", "weekly", SUNDAY) in messages()
    assert "Sent 3 weekly digests" in output


def test_families_that_had_not_started_are_skipped(today, families):
    Family.objects.create(name="Newcomers", start_date=MONDAY, invite_code="NEW001")
    output = send_digests("weekly")
    assert "Newcomers (not started yet)" in output
    assert "Newcomers" not in [name for name, _, _ in messages()]


def test_as_of_option(today, families):
    send_digests("weekly", "--as-of", "2026-10-11")
    assert {as_of for _, _, as_of in messages()} == {date(2026, 10, 11)}
    assert Message.objects.first().text.startswith("🏆 Weekly Steps — Oct 5–11")


def test_one_failing_family_does_not_stop_the_others(today, families, monkeypatch, caplog):
    real_send_digest = digests.send_digest

    def fail_for_spencers(family, kind, as_of):
        if family.name == "Spencers":
            raise RuntimeError("simulated failure")
        return real_send_digest(family, kind, as_of)

    monkeypatch.setattr(digests, "send_digest", fail_for_spencers)
    with pytest.raises(CommandError, match="1 of 2 digests failed"), caplog.at_level(logging.ERROR):
        send_digests("weekly")
    assert messages() == [("Grandparents", "weekly", SUNDAY)]
    assert "The weekly digest for Spencers" in caplog.text

    monkeypatch.setattr(digests, "send_digest", real_send_digest)  # the next run retries the family that failed
    assert "Spencers: not configured" in send_digests("weekly")
    assert ("Spencers", "weekly", SUNDAY) in messages()


def test_discord_status_is_reported(today, families, settings, monkeypatch):
    settings.DISCORD_WEBHOOK_URL = "https://discord.test/api/webhooks/1/token"
    monkeypatch.setattr(
        "leaderboard.discord.httpx.post",
        lambda url, json, timeout: httpx.Response(204, request=httpx.Request("POST", url)),
    )
    output = send_digests("weekly")
    assert "Spencers: sent" in output
    assert set(Message.objects.values_list("discord_status", flat=True)) == {"sent"}


def test_bad_arguments():
    with pytest.raises(CommandError, match="invalid choice"):
        send_digests("daily")
    with pytest.raises(CommandError, match="--as-of"):
        send_digests("weekly", "--as-of", "soon")


# --- The schedule ---------------------------------------------------------------------------------


def eastern(*args) -> datetime:
    return datetime(*args, tzinfo=EASTERN)


@pytest.mark.parametrize(
    ("now", "weekly", "monthly"),
    [
        # Monday afternoon: next Monday, and Nov 1 (after the switch to standard time).
        (eastern(2026, 10, 19, 17, 0), eastern(2026, 10, 26, 8, 0), eastern(2026, 11, 1, 8, 0)),
        # A minute before 8:00 on a Monday: today.
        (eastern(2026, 10, 26, 7, 59), eastern(2026, 10, 26, 8, 0), eastern(2026, 11, 1, 8, 0)),
        # March 1, 2027 is a Monday: both jobs fire at the same moment.
        (eastern(2027, 2, 28, 12, 0), eastern(2027, 3, 1, 8, 0), eastern(2027, 3, 1, 8, 0)),
    ],
    ids=["monday afternoon", "monday 7:59", "1st is a monday"],
)
def test_next_runs(now, weekly, monthly):
    runs = next_runs(now)
    assert (runs["weekly"], runs["monthly"]) == (weekly, monthly)
    assert runs["monthly"].utcoffset() == monthly.utcoffset()  # 8:00 local time, in EST or EDT as appropriate


def test_monthly_after_daylight_saving_ends_is_8am_standard_time():
    assert next_runs(eastern(2026, 10, 19, 17, 0))["monthly"].strftime("%H:%M %Z") == "08:00 EST"


def test_job_options():
    sched = build_scheduler(BackgroundScheduler)
    sched.start(paused=True)
    try:
        jobs = {job.id: job for job in sched.get_jobs()}
        assert set(jobs) == {"weekly-digests", "monthly-digests"}
        for job in jobs.values():
            assert (job.misfire_grace_time, job.coalesce, job.max_instances) == (MISFIRE_GRACE_SECONDS, True, 1)
    finally:
        sched.shutdown(wait=False)


def test_jobs_run_one_at_a_time(monkeypatch):
    """When the 1st is a Monday both jobs fire at 8:00. They must not overlap: on SQLite, one would fail."""
    spans, lock = [], threading.Lock()

    def slow_job(kind):
        start = time.monotonic()
        time.sleep(0.3)
        with lock:
            spans.append((start, time.monotonic()))

    monkeypatch.setattr(scheduler, "run_scheduled_digests", slow_job)
    sched = build_scheduler(BackgroundScheduler)
    sched.start(paused=True)
    now = datetime.now(EASTERN)
    for job in sched.get_jobs():
        job.modify(next_run_time=now)
    sched.resume()
    deadline = time.monotonic() + 5
    while len(spans) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    sched.shutdown()

    assert len(spans) == 2
    (first_start, first_end), (second_start, _) = sorted(spans)
    assert second_start >= first_end


# --- One scheduled run ----------------------------------------------------------------------------


def test_a_scheduled_run_counts_through_yesterday(db, today, monkeypatch):  # db: it refreshes connections
    calls = []
    monkeypatch.setattr(scheduler, "send_scheduled_digests", lambda kind, as_of: calls.append((kind, as_of)) or digests.ScheduledRun())
    scheduler.run_scheduled_digests("weekly")
    assert calls == [("weekly", SUNDAY)]


def test_a_scheduled_run_never_raises(db, today, monkeypatch, caplog):
    def broken(kind, as_of):
        raise RuntimeError("database down")

    monkeypatch.setattr(scheduler, "send_scheduled_digests", broken)
    with caplog.at_level(logging.ERROR, logger="leaderboard.scheduler"):
        scheduler.run_scheduled_digests("monthly")  # no exception: the schedule keeps running
    assert "The scheduled monthly digests failed" in caplog.text


def test_httpx_request_logging_is_off():
    """httpx logs each request's full URL at INFO; for Discord that URL is the webhook secret."""
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
