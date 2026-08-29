"""Tests for value breakdown + league validation."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import Instrument, PlayerGame
from app.services.player_analysis import league_validation, value_breakdown_for


def _player(db, symbol="NBA:1", name="Star") -> Instrument:
    inst = Instrument(symbol=symbol, name=name, currency="CAD", asset_class="PLAYER")
    db.add(inst)
    db.commit()
    return inst


def _games(db, inst, n, pts, reb=6, ast=5, tov=2):
    for i in range(n):
        db.add(
            PlayerGame(
                instrument_id=inst.id, espn_event_id=f"{inst.symbol}-{i}",
                game_date=date(2026, 1, 1) + timedelta(days=i), opponent="X", home=True,
                minutes=34, points=pts, rebounds=reb, assists=ast,
                steals=1, blocks=0.5, turnovers=tov,
            )
        )
    db.commit()


def test_breakdown_reconciles_to_value(db_session):
    inst = _player(db_session)
    _games(db_session, inst, n=20, pts=30)
    b = value_breakdown_for(db_session, inst.id)

    assert b.available and b.games == 20
    # Positive components sum + turnovers ~= base value (within rounding).
    assert abs(sum(b.components.values()) - b.base_value) < 1.0
    # base + form adjustment == final (within rounding).
    assert abs(b.base_value + b.form_adjustment - b.final_value) < 1.0
    assert b.averages["points"] == 30.0
    assert b.components["turnovers"] < 0  # turnovers subtract


def test_breakdown_unavailable_without_games(db_session):
    inst = _player(db_session)
    assert value_breakdown_for(db_session, inst.id).available is False


def test_validation_flags_small_sample(db_session):
    reliable = _player(db_session, "NBA:R", "Reliable Star")
    _games(db_session, reliable, n=40, pts=25)
    role = _player(db_session, "NBA:B", "Bench Guy")
    _games(db_session, role, n=30, pts=8, reb=3, ast=1)
    small = _player(db_session, "NBA:S", "One Game Wonder")
    _games(db_session, small, n=1, pts=40, reb=20, ast=10)  # inflated on 1 game

    v = league_validation(db_session)
    top_names = {r.name for r in v.top}
    watch_names = {r.name for r in v.watchouts}

    assert "Reliable Star" in top_names  # enough games -> ranked
    assert "One Game Wonder" not in top_names  # excluded from reliable top
    assert "One Game Wonder" in watch_names  # surfaced as a small-sample watch-out
    assert v.corr_value_production is not None
