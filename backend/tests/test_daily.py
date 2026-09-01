"""Player-pack economy tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import Instrument, PriceBar, Position
from app.services import bootstrap
from app.services.daily import COOLDOWN, OnCooldown, claim, status


def _player(db, symbol, name, price):
    i = Instrument(symbol=symbol, name=name, currency="CAD", asset_class="PLAYER", sport="NBA")
    db.add(i)
    db.commit()
    db.add(
        PriceBar(
            instrument_id=i.id, bar_date=date(2026, 4, 1), close=Decimal(str(price)), currency="CAD",
            source="espn", as_of=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    return i


def _user_with_team(db):
    u = bootstrap.create_user(db, email="p@x.io", display_name="p")
    pf = bootstrap.create_portfolio(db, user_id=u.id, name="p team")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("0"), currency="CAD")
    return u, pf


def test_pack_grants_a_player_worth_about_1000(db_session):
    _player(db_session, "NBA:A", "Star A", 500)
    _player(db_session, "NBA:B", "Role B", 120)
    u, pf = _user_with_team(db_session)

    res = claim(db_session, u, now=datetime(2026, 5, 1, tzinfo=timezone.utc))
    assert res.shares >= 1
    assert 700 <= res.value <= 1300  # ~$1,000 of the pulled player
    # A position was granted to the team.
    pos = db_session.query(Position).filter_by(portfolio_id=pf.id).all()
    assert len(pos) == 1 and float(pos[0].quantity) == res.shares


def test_cannot_open_within_cooldown(db_session):
    _player(db_session, "NBA:A", "A", 300)
    u, _ = _user_with_team(db_session)
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    claim(db_session, u, now=t0)
    with pytest.raises(OnCooldown):
        claim(db_session, u, now=t0 + timedelta(hours=6))  # < 12h


def test_can_open_again_after_cooldown(db_session):
    _player(db_session, "NBA:A", "A", 300)
    u, _ = _user_with_team(db_session)
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    claim(db_session, u, now=t0)
    r2 = claim(db_session, u, now=t0 + COOLDOWN + timedelta(minutes=1))
    assert r2.streak == 2  # consecutive within 40h


def test_status_shows_cooldown(db_session):
    _player(db_session, "NBA:A", "A", 300)
    u, _ = _user_with_team(db_session)
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    assert status(db_session, u, now=t0).can_claim is True
    claim(db_session, u, now=t0)
    st = status(db_session, u, now=t0 + timedelta(hours=3))
    assert st.can_claim is False and st.seconds_remaining > 0
