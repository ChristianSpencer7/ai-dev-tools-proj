"""The database itself enforces the step entry rules, not just the API."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from leaderboard.models import Family, Member, StepEntry

DAY = date(2026, 10, 12)


@pytest.fixture
def family(db):
    return Family.objects.create(name="Demo Family", start_date=date(2026, 9, 14), invite_code="DEMO")


@pytest.fixture
def member(family):
    return Member.objects.create(family=family, name="Dad")


def rejected():
    """Expect the database to refuse a write.

    Use with transaction.atomic(), whose savepoint keeps the test's transaction usable afterwards.
    """
    return pytest.raises(IntegrityError)


def test_one_entry_per_member_per_day(member):
    StepEntry.objects.create(member=member, day=DAY, steps=5_000)
    with rejected(), transaction.atomic():
        StepEntry.objects.create(member=member, day=DAY, steps=9_000)
    assert StepEntry.objects.get(member=member, day=DAY).steps == 5_000


def test_other_members_and_days_are_separate(family, member):
    mom = Member.objects.create(family=family, name="Mom")
    StepEntry.objects.create(member=member, day=DAY, steps=5_000)
    StepEntry.objects.create(member=mom, day=DAY, steps=6_000)
    StepEntry.objects.create(member=member, day=date(2026, 10, 13), steps=7_000)
    assert StepEntry.objects.count() == 3


@pytest.mark.parametrize("steps", [0, 100_000])
def test_steps_limits_are_allowed(member, steps):
    StepEntry.objects.create(member=member, day=DAY, steps=steps)


@pytest.mark.parametrize("steps", [-1, 100_001])
def test_steps_outside_range_are_rejected(member, steps):
    with rejected(), transaction.atomic():
        StepEntry.objects.create(member=member, day=DAY, steps=steps)


def test_step_limit_error_message(member):
    with pytest.raises(ValidationError) as error:
        StepEntry(member=member, day=DAY, steps=100_001).validate_constraints()
    assert error.value.messages == ["Steps must be 100,000 or fewer."]


def test_invite_codes_are_unique(family):
    with rejected(), transaction.atomic():
        Family.objects.create(name="Copycats", start_date=date(2026, 10, 1), invite_code="DEMO")


def test_deleting_a_family_deletes_its_members_and_steps(family, member):
    StepEntry.objects.create(member=member, day=DAY, steps=5_000)
    family.delete()
    assert not Member.objects.exists()
    assert not StepEntry.objects.exists()
