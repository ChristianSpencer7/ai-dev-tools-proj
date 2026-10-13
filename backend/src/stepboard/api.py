"""HTTP API. The routes here must match openapi.yaml (checked by tests/test_contract.py)."""

import secrets
from collections.abc import Iterator
from datetime import date, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from stepboard import db, schemas
from stepboard.config import Settings, today_eastern
from stepboard.digests import send_digest
from stepboard.reports import alltime_board, weekly_board

# No 0/O or 1/I, so codes are easy to read aloud.
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_invite_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def get_family(family_id: int, session: Session = Depends(get_session)) -> db.Family:
    family = session.get(db.Family, family_id)
    if family is None:
        raise HTTPException(404, "Family not found")
    return family


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Family Step Leaderboard API", version="0.2.0")
    app.state.settings = settings
    app.state.sessions = sessionmaker(db.make_engine(settings.database_url), expire_on_commit=False)

    @app.get("/health", response_model=schemas.Health)
    def health(session: Session = Depends(get_session)):
        session.execute(text("SELECT 1"))
        return {"ok": True}

    @app.get("/families", response_model=list[schemas.FamilySummary])
    def list_families(session: Session = Depends(get_session)):
        return session.scalars(select(db.Family).order_by(db.Family.id)).all()

    @app.post("/families", response_model=schemas.Family, status_code=201)
    def create_family(body: schemas.FamilyCreate, session: Session = Depends(get_session)):
        family = db.Family(
            name=body.name.strip(),
            start_date=body.start_date or today_eastern(),
            invite_code=new_invite_code(),
        )
        session.add(family)
        session.commit()
        return family

    @app.post("/families/join", response_model=schemas.Member, status_code=201)
    def join_family(body: schemas.JoinRequest, session: Session = Depends(get_session)):
        code = body.invite_code.strip().upper()
        family = session.scalar(select(db.Family).where(db.Family.invite_code == code))
        if family is None:
            raise HTTPException(404, "No family has that invite code")
        member = db.Member(family_id=family.id, name=body.name.strip())
        session.add(member)
        session.commit()
        return member

    @app.get("/families/{family_id}", response_model=schemas.Family)
    def get_family_route(family: db.Family = Depends(get_family)):
        return family

    @app.get("/families/{family_id}/members", response_model=list[schemas.Member])
    def list_members(family: db.Family = Depends(get_family), session: Session = Depends(get_session)):
        query = select(db.Member).where(db.Member.family_id == family.id).order_by(db.Member.name)
        return session.scalars(query).all()

    @app.get("/members/{member_id}/steps", response_model=list[schemas.StepEntry])
    def list_member_steps(
        member_id: int,
        start: date | None = Query(None, alias="from"),
        end: date | None = Query(None, alias="to"),
        session: Session = Depends(get_session),
    ):
        if session.get(db.Member, member_id) is None:
            raise HTTPException(404, "Member not found")
        end = end or today_eastern()
        start = start or end - timedelta(days=13)
        query = (
            select(db.StepEntry)
            .where(db.StepEntry.member_id == member_id, db.StepEntry.day.between(start, end))
            .order_by(db.StepEntry.day.desc())
        )
        return session.scalars(query).all()

    @app.post("/steps", response_model=list[schemas.StepEntry])
    def log_steps(body: schemas.StepsImport, session: Session = Depends(get_session)):
        if session.get(db.Member, body.member_id) is None:
            raise HTTPException(404, "Member not found")
        today = today_eastern()
        if future := [e.day.isoformat() for e in body.entries if e.day > today]:
            raise HTTPException(422, f"These days haven't happened yet: {', '.join(future)}")
        saved = [db.record_steps(session, body.member_id, e.day, e.steps, body.source) for e in body.entries]
        session.commit()
        return saved

    @app.get("/families/{family_id}/leaderboards/weekly", response_model=schemas.Leaderboard)
    def weekly_leaderboard(
        as_of: date | None = None,
        family: db.Family = Depends(get_family),
        session: Session = Depends(get_session),
    ):
        return weekly_board(session, family, as_of or today_eastern())

    @app.get("/families/{family_id}/leaderboards/all-time", response_model=schemas.Leaderboard)
    def alltime_leaderboard(
        as_of: date | None = None,
        family: db.Family = Depends(get_family),
        session: Session = Depends(get_session),
    ):
        return alltime_board(session, family, as_of or today_eastern())

    @app.get("/families/{family_id}/messages", response_model=list[schemas.Message])
    def list_messages(family: db.Family = Depends(get_family), session: Session = Depends(get_session)):
        query = (
            select(db.Message)
            .where(db.Message.family_id == family.id)
            .order_by(db.Message.created_at.desc(), db.Message.id.desc())
        )
        return session.scalars(query).all()

    @app.post("/families/{family_id}/digests", response_model=schemas.Message, status_code=201)
    def create_digest(
        body: schemas.DigestRequest,
        family: db.Family = Depends(get_family),
        session: Session = Depends(get_session),
    ):
        as_of = body.as_of or today_eastern()
        return send_digest(session, family, body.kind, as_of, settings.discord_webhook_url)

    return app
