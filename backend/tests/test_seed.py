"""The demo family seed, and the seed_demo management command."""

from collections import defaultdict
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from leaderboard.models import Family, Member, StepEntry
from leaderboard.ranking import assign_ranks, week_start
from leaderboard.seed import DEMO_INVITE_CODE, DEMO_MEMBERS, seed_demo_family
from leaderboard.serializers import MAX_DAILY_STEPS

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 14)  # a Wednesday
START = date(2026, 9, 14)  # the Monday 4 weeks before TODAY's week


def all_entries() -> list[tuple]:
    return sorted(StepEntry.objects.values_list("member__name", "day", "steps", "source"))


# --- seed_demo_family ----------------------------------------------------------------------------


def test_creates_the_demo_family():
    family = seed_demo_family(TODAY)
    assert (family.name, family.invite_code, family.start_date) == ("Demo Family", DEMO_INVITE_CODE, START)
    assert sorted(family.members.values_list("name", flat=True)) == sorted(DEMO_MEMBERS)


def test_every_member_has_every_day_through_today():
    family = seed_demo_family(TODAY)
    expected_days = {START + timedelta(days=n) for n in range((TODAY - START).days + 1)}
    for member in family.members.all():
        assert set(member.steps.values_list("day", flat=True)) == expected_days
    assert set(StepEntry.objects.values_list("source", flat=True)) == {"seed"}


def test_steps_are_in_range_and_today_is_partial():
    seed_demo_family(TODAY)
    assert all(0 <= steps <= MAX_DAILY_STEPS for steps in StepEntry.objects.values_list("steps", flat=True))
    for member in Member.objects.all():
        earlier = list(member.steps.exclude(day=TODAY).values_list("steps", flat=True))
        today = member.steps.get(day=TODAY).steps
        assert today < 0.7 * sum(earlier) / len(earlier)  # the day isn't over yet


def test_the_same_date_gives_the_same_data():
    seed_demo_family(TODAY)
    first = all_entries()
    Family.objects.all().delete()
    seed_demo_family(TODAY)
    assert all_entries() == first


def test_runs_only_once():
    seed_demo_family(TODAY)
    before = all_entries()
    assert seed_demo_family(TODAY) is None
    assert all_entries() == before
    assert Family.objects.count() == 1


def test_seeded_on_a_monday_this_week_still_has_steps():
    monday = date(2026, 10, 12)
    family = seed_demo_family(monday)
    this_week = dict(StepEntry.objects.filter(day=monday).values_list("member__name", "steps"))
    assert set(this_week) == set(DEMO_MEMBERS)
    assert all(steps > 0 for steps in this_week.values())
    assert family.start_date == date(2026, 9, 14)


def test_ranks_change_between_weeks():
    """Different trends make the weekly order move, so the boards have rank changes to show."""
    seed_demo_family(TODAY)
    weekly = defaultdict(lambda: defaultdict(int))
    for name, day, steps in StepEntry.objects.values_list("member__name", "day", "steps"):
        weekly[week_start(day)][name] += steps
    full_weeks = [monday for monday in sorted(weekly) if monday < week_start(TODAY)]
    orders = [tuple(sorted(weekly[m], key=assign_ranks(weekly[m]).get)) for m in full_weeks]
    assert len(full_weeks) == 4
    assert len(set(orders)) > 1


# --- seed_demo command ---------------------------------------------------------------------------


@pytest.fixture
def pinned_today(monkeypatch):
    monkeypatch.setattr("leaderboard.management.commands.seed_demo.today_eastern", lambda: TODAY)


def seed_demo(*args) -> str:
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


def test_command_seeds_once(pinned_today):
    assert "Seeded Demo Family (invite code DEMO): 4 members, steps from 2026-09-14 through 2026-10-14." in seed_demo()
    assert "already exists; nothing to do" in seed_demo()
    assert Family.objects.count() == 1


def test_command_reset_replaces_the_demo_family_only(pinned_today):
    other = Family.objects.create(name="Spencers", start_date=date(2026, 10, 1), invite_code="KEEP01")
    seed_demo()
    fresh = all_entries()
    StepEntry.objects.update(steps=1)

    output = seed_demo("--reset")

    assert "Deleted the existing Demo Family." in output
    assert "Seeded Demo Family" in output
    assert all_entries() == fresh
    assert Family.objects.filter(pk=other.pk).exists()
    assert Family.objects.count() == 2


def test_command_reset_without_a_demo_family(pinned_today):
    output = seed_demo("--reset")
    assert "Deleted" not in output
    assert Family.objects.filter(invite_code=DEMO_INVITE_CODE).exists()
