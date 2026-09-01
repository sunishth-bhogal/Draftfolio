"""Pack store tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import CashBalance, Instrument, PriceBar, Position
from app.services import bootstrap
from app.services.store import NotEnoughCash, RARITY_ORDER, TIER_BY_KEY, open_pack


def _player(db, symbol, name, price):
    i = Instrument(symbol=symbol, name=name, currency="CAD", asset_class="PLAYER", sport="NHL")
    db.add(i)
    db.commit()
    db.add(PriceBar(instrument_id=i.id, bar_date=date(2026, 4, 1), close=Decimal(str(price)),
                    currency="CAD", source="espn", as_of=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    db.commit()
    return i


def _funded_user(db, cash):
    u = bootstrap.create_user(db, email="s@x.io", display_name="s")
    pf = bootstrap.create_portfolio(db, user_id=u.id, name="s team")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal(str(cash)), currency="CAD")
    return u, pf


def _market(db):
    # players across rarity bands
    _player(db, "NHL:C1", "Common1", 120)
    _player(db, "NHL:C2", "Common2", 200)
    _player(db, "NHL:R1", "Rare1", 420)
    _player(db, "NHL:E1", "Epic1", 580)
    _player(db, "NHL:L1", "Legend1", 720)


def test_open_debits_cash_and_grants_cards(db_session):
    _market(db_session)
    u, pf = _funded_user(db_session, 5000)
    res = open_pack(db_session, u, "gold")  # cost 1500, 3 cards

    assert len(res.cards) == 3
    assert res.cash == 5000 - TIER_BY_KEY["gold"].cost  # cash debited
    cb = db_session.get(CashBalance, {"portfolio_id": pf.id, "currency": "CAD"})
    assert float(cb.amount) == 3500
    # 3 cards granted as positions
    total_shares = sum(float(p.quantity) for p in db_session.query(Position).filter_by(portfolio_id=pf.id))
    assert total_shares == 3


def test_gold_guarantees_epic(db_session):
    _market(db_session)
    u, _ = _funded_user(db_session, 5000)
    res = open_pack(db_session, u, "gold")
    gi = RARITY_ORDER.index("epic")
    assert any(RARITY_ORDER.index(c.tier) >= gi for c in res.cards)


def test_cannot_open_without_cash(db_session):
    _market(db_session)
    u, _ = _funded_user(db_session, 100)  # < any pack
    with pytest.raises(NotEnoughCash):
        open_pack(db_session, u, "gold")


def test_cheaper_tiers_are_affordable(db_session):
    _market(db_session)
    u, _ = _funded_user(db_session, 250)  # exactly a bronze
    res = open_pack(db_session, u, "bronze")
    assert len(res.cards) == 1 and res.cash == 0
