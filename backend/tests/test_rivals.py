"""Rivals ladder: XP, levels, gameweek scoring, promotion/relegation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import Instrument, PriceBar, User
from app.services import auth as auth_svc
from app.services import bootstrap
from app.services.orders import place_order
from app.services.rivals import (
    DIVISIONS,
    _promote,
    _relegate,
    division_standings,
    level_for_xp,
    run_gameweek,
)


def test_level_for_xp():
    assert level_for_xp(0) == 1
    assert level_for_xp(499) == 1
    assert level_for_xp(500) == 2
    assert level_for_xp(1250) == 3


def test_promote_relegate_bounds():
    assert _promote("Bronze") == "Silver"
    assert _promote("Diamond") == "Diamond"  # capped
    assert _relegate("Silver") == "Bronze"
    assert _relegate("Bronze") == "Bronze"  # floored


def _rival(db, username, div="Bronze"):
    u = User(email=f"{username}@r.io", display_name=username, username=username,
             password_hash=auth_svc.hash_password("password"), division=div)
    db.add(u)
    db.commit()
    return u


def _team_with_gain(client, db, user, symbol, entry, exit_price):
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if inst is None:
        inst = Instrument(symbol=symbol, name=symbol, currency="CAD", asset_class="PLAYER", sport="NBA")
        db.add(inst); db.commit()
    pf = bootstrap.create_portfolio(db, user_id=user.id, name=f"{user.username} team")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD")
    place_order(db, portfolio_id=pf.id, idempotency_key=f"{pf.id}-{symbol}", side="BUY",
                symbol=symbol, quantity=Decimal("100"), price=Decimal(str(entry)), currency="CAD", fee=Decimal("0"))
    for d, px in [(date(2026, 1, 1), entry), (date(2026, 1, 15), exit_price)]:
        db.add(PriceBar(instrument_id=inst.id, bar_date=d, close=Decimal(str(px)), currency="CAD",
                        source="espn", as_of=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)))
    db.commit()
    return pf


def test_gameweek_awards_and_ranks(client, db_session):
    winner = _rival(db_session, "winner")
    loser = _rival(db_session, "loser")
    _team_with_gain(client, db_session, winner, "NBA:W", entry=100, exit_price=130)  # +30%
    _team_with_gain(client, db_session, loser, "NBA:L", entry=100, exit_price=95)  # -5%

    out = run_gameweek(db_session, number=1, start=date(2026, 1, 1), end=date(2026, 1, 15))
    assert out.scored == 2

    db_session.refresh(winner)
    db_session.refresh(loser)
    assert winner.xp > loser.xp  # winner earns more XP
    assert winner.division_points > loser.division_points  # and more ladder points

    standings = division_standings(db_session, "Bronze")
    assert standings[0].username == "winner"  # ranked first


def test_promotion_on_enough_points(client, db_session):
    u = _rival(db_session, "climber")
    u.division_points = 8  # near the promote threshold (10)
    db_session.commit()
    _team_with_gain(client, db_session, u, "NBA:C", entry=100, exit_price=150)  # big win -> +3 pts
    run_gameweek(db_session, number=2, start=date(2026, 1, 1), end=date(2026, 1, 15))
    db_session.refresh(u)
    assert u.division == "Silver"  # promoted
    assert u.division_points == 0  # reset
