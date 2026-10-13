from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from stepboard import db
from stepboard.api import create_app
from stepboard.config import Settings

START = date(2026, 9, 28)  # a Monday


@pytest.fixture
def session():
    sessions = sessionmaker(db.make_engine("sqlite:///:memory:"), expire_on_commit=False)
    with sessions() as s:
        yield s


@pytest.fixture
def family(session):
    """A family starting on START with Dad (id 1) and Mom (id 2)."""
    fam = db.Family(name="Test", start_date=START, invite_code="TEST01")
    session.add(fam)
    session.flush()
    session.add_all([db.Member(id=1, family_id=fam.id, name="Dad"), db.Member(id=2, family_id=fam.id, name="Mom")])
    session.commit()
    return fam


@pytest.fixture
def settings():
    return Settings(database_url="sqlite:///:memory:", discord_webhook_url=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c
