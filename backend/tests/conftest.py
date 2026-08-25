"""Test fixtures: an in-memory SQLite DB and a FastAPI TestClient.

The same ORM/service code runs against Postgres in production (via DATABASE_URL);
here we use SQLite so the full API path is verifiable without Docker. DecimalType
keeps money exact on both.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base
from app.services import bootstrap


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(db_session):
    """A user with a $100k CAD portfolio and one AAPL instrument."""
    user = bootstrap.create_user(db_session, email="a@b.com", display_name="Tester")
    inst = bootstrap.create_instrument(
        db_session, symbol="AAPL", name="Apple Inc.", currency="CAD", sector="Tech"
    )
    pf = bootstrap.create_portfolio(
        db_session, user_id=user.id, name="Playoffs", base_currency="CAD"
    )
    bootstrap.fund_portfolio(
        db_session, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD"
    )
    return {"user": user, "instrument": inst, "portfolio": pf}
