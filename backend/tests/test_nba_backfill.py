"""Tests for player price-history backfill (raw storage + versioned prices)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.domain.player_value import FORMULA_VERSION
from app.models import Instrument, PlayerGame, PriceBar
from app.services.nba_backfill import backfill_player
from app.services.nba_espn import GameObs


def _player(db) -> Instrument:
    inst = Instrument(symbol="NBA:1", name="Test Star", currency="CAD", asset_class="PLAYER")
    db.add(inst)
    db.commit()
    return inst


def _game(eid, d, pts) -> GameObs:
    return GameObs(
        espn_event_id=eid, game_date=d, opponent="X", home=True, minutes=34,
        points=pts, rebounds=6, assists=5, steals=1, blocks=0.5, turnovers=2,
    )


def test_backfill_stores_raw_and_versioned_prices(db_session):
    inst = _player(db_session)
    games = [
        _game("1", date(2026, 1, 1), 20),
        _game("2", date(2026, 1, 3), 40),
        _game("3", date(2026, 1, 5), 30),
    ]
    bars = backfill_player(db_session, inst, games)
    assert bars == 3

    raw = db_session.scalars(select(PlayerGame).where(PlayerGame.instrument_id == inst.id)).all()
    assert len(raw) == 3  # raw observations stored separately

    prices = db_session.scalars(
        select(PriceBar).where(PriceBar.instrument_id == inst.id).order_by(PriceBar.bar_date)
    ).all()
    assert len(prices) == 3
    assert all(p.formula_version == FORMULA_VERSION for p in prices)  # every price is versioned
    # A 40-point game lifts value above the 20-point opener.
    assert float(prices[1].close) > float(prices[0].close)


def test_backfill_dedupes_duplicate_events(db_session):
    inst = _player(db_session)
    games = [
        _game("1", date(2026, 1, 1), 20),
        _game("1", date(2026, 1, 1), 20),  # duplicate event (overlapping ESPN buckets)
        _game("2", date(2026, 1, 3), 40),
    ]
    bars = backfill_player(db_session, inst, games)
    assert bars == 2  # duplicate collapsed, no UniqueViolation
    raw = db_session.scalars(select(PlayerGame).where(PlayerGame.instrument_id == inst.id)).all()
    assert len(raw) == 2


def test_backfill_is_idempotent(db_session):
    inst = _player(db_session)
    games = [_game("1", date(2026, 1, 1), 20), _game("2", date(2026, 1, 3), 40)]
    backfill_player(db_session, inst, games)
    backfill_player(db_session, inst, games)  # rerun
    prices = db_session.scalars(select(PriceBar).where(PriceBar.instrument_id == inst.id)).all()
    assert len(prices) == 2  # updated in place, not duplicated
