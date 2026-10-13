"""Tables and queries. Postgres in docker compose, SQLite for tests and quick local runs."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from stepboard.leaderboard import DayRecord


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[date] = mapped_column(Date)
    invite_code: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StepEntry(Base):
    __tablename__ = "step_entries"
    __table_args__ = (CheckConstraint("steps >= 0", name="steps_not_negative"),)

    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)  # Eastern
    steps: Mapped[int]
    source: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # weekly, monthly
    text: Mapped[str] = mapped_column(Text)
    discord_status: Mapped[str] = mapped_column(String(16))  # not_configured, sent, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool  # one shared in-memory database
        engine = create_engine(url, **kwargs)
    else:
        engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def record_steps(session: Session, member_id: int, day: date, steps: int, source: str) -> StepEntry:
    """Store a day's total. A later value for the same day replaces the earlier one."""
    entry = session.get(StepEntry, (member_id, day))
    if entry is None:
        entry = StepEntry(member_id=member_id, day=day, steps=steps, source=source)
        session.add(entry)
    else:
        entry.steps, entry.source = steps, source
    return entry


def member_names(session: Session, family_id: int) -> dict[int, str]:
    rows = session.execute(select(Member.id, Member.name).where(Member.family_id == family_id))
    return {member_id: name for member_id, name in rows}


def totals(session: Session, family_id: int, start: date, end: date) -> dict[int, int]:
    """Total steps per member from start through end, inclusive."""
    rows = session.execute(
        select(StepEntry.member_id, func.sum(StepEntry.steps))
        .join(Member, Member.id == StepEntry.member_id)
        .where(Member.family_id == family_id, StepEntry.day.between(start, end))
        .group_by(StepEntry.member_id)
    )
    return {member_id: int(total) for member_id, total in rows}


def daily(session: Session, family_id: int, start: date, end: date) -> list[DayRecord]:
    rows = session.execute(
        select(StepEntry.member_id, StepEntry.day, StepEntry.steps)
        .join(Member, Member.id == StepEntry.member_id)
        .where(Member.family_id == family_id, StepEntry.day.between(start, end))
        .order_by(StepEntry.day)
    )
    return [DayRecord(member_id, day, steps) for member_id, day, steps in rows]
