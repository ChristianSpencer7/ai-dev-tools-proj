"""Request and response bodies. Keep these in step with openapi.yaml."""

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_DAILY_STEPS = 100_000

StepSource = Literal["manual", "import", "seed", "shortcut", "fitbit", "garmin"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Health(BaseModel):
    ok: bool


class FamilySummary(ORMModel):
    id: int
    name: str
    start_date: date


class Family(FamilySummary):
    invite_code: str


class FamilyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start_date: date | None = None


class JoinRequest(BaseModel):
    invite_code: str
    name: str = Field(min_length=1, max_length=40)


class Member(ORMModel):
    id: int
    family_id: int
    name: str


class StepEntryIn(BaseModel):
    day: date
    steps: int = Field(ge=0, le=MAX_DAILY_STEPS)


class StepsImport(BaseModel):
    member_id: int
    source: StepSource = "manual"
    entries: list[StepEntryIn] = Field(min_length=1, max_length=366)


class StepEntry(ORMModel):
    member_id: int
    day: date
    steps: int
    source: StepSource


class Standing(ORMModel):
    member_id: int
    name: str
    steps: int
    rank: int
    medal: str | None
    prev_rank: int | None
    step_change: int | None


class Callout(ORMModel):
    kind: Literal["best_single_day", "most_improved"]
    text: str


class Leaderboard(ORMModel):
    kind: Literal["weekly", "all_time"]
    title: str
    start: date
    end: date
    has_comparison: bool
    standings: list[Standing]
    callouts: list[Callout]


class DigestRequest(BaseModel):
    kind: Literal["weekly", "monthly"]
    as_of: date | None = None


class Message(ORMModel):
    id: int
    family_id: int
    kind: Literal["weekly", "monthly"]
    text: str
    created_at: datetime
    discord_status: Literal["not_configured", "sent", "failed"]

    @field_validator("created_at")
    @classmethod
    def as_utc(cls, value: datetime) -> datetime:
        # SQLite returns naive datetimes; they are stored in UTC.
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
