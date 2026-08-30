"""Tests for the daily price catalyst system."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import Instrument, PlayerGame, SignalEvent
from app.services.catalysts import player_catalysts, write_catalyst_signal


def _player(db, injury=None) -> Instrument:
    inst = Instrument(
        symbol="NBA:1", name="Test Player", currency="CAD", asset_class="PLAYER",
        position="G", injury_status=injury,
    )
    db.add(inst)
    db.commit()
    return inst


def _game(inst, i, pts, mins=32, opp="LAL"):
    return PlayerGame(
        instrument_id=inst.id, espn_event_id=f"e{i}", game_date=date(2026, 1, 1) + timedelta(days=i),
        opponent=opp, home=True, minutes=mins, points=pts, rebounds=4, assists=5,
        steals=1, blocks=0.5, turnovers=2,
    )


def test_big_game_is_an_up_catalyst(db_session):
    inst = _player(db_session)
    for i in range(9):
        db_session.add(_game(inst, i, pts=15))  # modest baseline
    db_session.add(_game(inst, 9, pts=45, mins=40, opp="BOS"))  # explosion
    db_session.commit()

    c = player_catalysts(db_session, inst.id)
    assert c.available
    perf = next(x for x in c.items if x.kind == "performance")
    assert perf.direction == "up" and "45 PTS" in perf.detail
    # Elevated minutes should also register.
    assert any(x.kind == "minutes" and x.direction == "up" for x in c.items)
    # Opponent context present.
    assert any(x.kind == "schedule" and "BOS" in x.label for x in c.items)


def test_injury_is_an_availability_catalyst(db_session):
    inst = _player(db_session, injury="Out")
    for i in range(5):
        db_session.add(_game(inst, i, pts=20))
    db_session.commit()
    c = player_catalysts(db_session, inst.id)
    assert any(x.kind == "availability" and "Out" in x.label for x in c.items)


def test_write_catalyst_signal_for_notable_game(db_session):
    inst = _player(db_session)
    for i in range(9):
        db_session.add(_game(inst, i, pts=12))
    db_session.add(_game(inst, 9, pts=40))
    db_session.commit()

    sig = write_catalyst_signal(db_session, inst)
    db_session.commit()
    assert sig is not None
    rows = db_session.query(SignalEvent).filter_by(instrument_id=inst.id).all()
    assert len(rows) == 1 and rows[0].source == "catalyst"


def test_no_games_no_catalysts(db_session):
    inst = _player(db_session)
    assert player_catalysts(db_session, inst.id).available is False
