"""Tests for player-index ETFs (baskets priced from constituents)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models import Instrument, PriceBar
from app.services.etf import backfill_etf, define_etf, etf_composition


def _player(db, symbol, name):
    inst = Instrument(symbol=symbol, name=name, currency="CAD", asset_class="PLAYER", sport="NBA")
    db.add(inst)
    db.commit()
    return inst


def _bar(db, inst, d, close):
    db.add(
        PriceBar(
            instrument_id=inst.id, bar_date=d, close=Decimal(str(close)), currency="CAD",
            source="espn", formula_version="v2",
            as_of=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
        )
    )
    db.commit()


def test_etf_price_is_basket_mean(db_session):
    a = _player(db_session, "NBA:A", "Player A")
    b = _player(db_session, "NBA:B", "Player B")
    _bar(db_session, a, date(2026, 1, 1), 100)
    _bar(db_session, b, date(2026, 1, 1), 300)
    _bar(db_session, a, date(2026, 1, 2), 120)  # b carries forward at 300

    etf = define_etf(db_session, symbol="TESTX", name="Test Index", sport="NBA", members=[a, b])
    n = backfill_etf(db_session, etf)
    assert n == 2

    bars = {
        pb.bar_date: float(pb.close)
        for pb in db_session.query(PriceBar).filter_by(instrument_id=etf.id, source="etf")
    }
    assert bars[date(2026, 1, 1)] == 200.0  # (100 + 300) / 2
    assert bars[date(2026, 1, 2)] == 210.0  # (120 + 300 carried) / 2


def test_weighted_etf(db_session):
    a = _player(db_session, "NBA:A", "A")
    b = _player(db_session, "NBA:B", "B")
    _bar(db_session, a, date(2026, 1, 1), 100)
    _bar(db_session, b, date(2026, 1, 1), 200)
    etf = define_etf(db_session, symbol="WX", name="Weighted", sport="NBA", members=[a, b], weights=[3.0, 1.0])
    backfill_etf(db_session, etf)
    bar = db_session.query(PriceBar).filter_by(instrument_id=etf.id, source="etf").one()
    assert float(bar.close) == 125.0  # (3*100 + 1*200) / 4


def test_composition(db_session):
    a = _player(db_session, "NBA:A", "Alpha")
    b = _player(db_session, "NBA:B", "Beta")
    _bar(db_session, a, date(2026, 1, 1), 100)
    _bar(db_session, b, date(2026, 1, 1), 300)
    etf = define_etf(db_session, symbol="CX", name="Comp", sport="NBA", members=[a, b])
    comp = etf_composition(db_session, etf.id)
    assert comp.available and comp.count == 2
    assert comp.constituents[0].name == "Beta"  # sorted by value desc
    assert abs(comp.constituents[0].weight_pct - 50.0) < 0.1


def test_composition_unavailable_for_non_etf(db_session):
    a = _player(db_session, "NBA:A", "A")
    assert etf_composition(db_session, a.id).available is False
