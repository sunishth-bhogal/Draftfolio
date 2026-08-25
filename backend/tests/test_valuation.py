"""Tests for price ingestion, valuation, point-in-time safety, and returns."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services import valuation as val
from app.services.prices import ingest_bars


def _buy(client, pf_id, qty, price, key):
    return client.post(
        f"/portfolios/{pf_id}/orders",
        json={"side": "BUY", "symbol": "AAPL", "quantity": qty, "price": price, "fee": 0},
        headers={"Idempotency-Key": key},
    )


def test_valuation_equals_cash_plus_market_value(client, seeded, db_session):
    pf = seeded["portfolio"]
    _buy(client, pf.id, 10, 150, "b1")  # spend 1500, cash -> 98500
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 25), Decimal("160"))])

    r = client.get(f"/portfolios/{pf.id}/valuation").json()
    assert r["cash"] == 98500.0
    assert r["market_value"] == 1600.0  # 10 * 160
    assert r["equity"] == 100100.0  # cash + market value
    assert r["holdings"][0]["symbol"] == "AAPL"
    # weight is reported rounded to 4 decimals (0.0160)
    assert abs(r["holdings"][0]["weight"] - (1600.0 / 100100.0)) < 1e-4


def test_point_in_time_excludes_future_data(client, seeded, db_session):
    """A bar whose as_of is in the future must not be used for valuation now."""
    pf = seeded["portfolio"]
    _buy(client, pf.id, 10, 150, "b1")

    now = datetime.now(timezone.utc)
    # Known price (available), plus a "tomorrow" price not yet available.
    ingest_bars(
        db_session,
        symbol="AAPL",
        bars=[(date(2026, 8, 25), Decimal("160"))],
        as_of=now - timedelta(days=1),
    )
    ingest_bars(
        db_session,
        symbol="AAPL",
        bars=[(date(2026, 8, 26), Decimal("999"))],
        source="future",
        as_of=now + timedelta(days=1),  # not known yet
    )

    v = val.value_portfolio(db_session, pf.id, "CAD", as_of=now)
    # Uses 160, never the look-ahead 999.
    assert v.market_value == Decimal("1600.0000")


def test_snapshot_and_return_series(client, seeded, db_session):
    pf = seeded["portfolio"]
    _buy(client, pf.id, 10, 150, "b1")

    # Day 1 mark 150 -> equity 100000; Day 2 mark 165 -> equity 100150.
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 24), Decimal("150"))])
    val.take_snapshot(db_session, pf.id, "CAD", date(2026, 8, 24))
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 25), Decimal("165"))])
    val.take_snapshot(db_session, pf.id, "CAD", date(2026, 8, 25))

    series = val.return_series(db_session, pf.id)
    assert len(series) == 2
    assert series[0].daily_return is None  # first point
    assert series[0].equity == Decimal("100000.0000")
    assert series[1].equity == Decimal("100150.0000")
    # daily return = 100150/100000 - 1 = 0.0015
    assert series[1].daily_return == Decimal("0.001500")
    assert series[1].cumulative_return == Decimal("0.001500")


def test_ingest_is_idempotent(client, seeded, db_session):
    n1 = ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 25), Decimal("160"))])
    n2 = ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 25), Decimal("161"))])
    assert n1 == 1 and n2 == 1
    # Same (instrument, date, source) updated, not duplicated.
    price = val.latest_close(
        db_session, seeded["instrument"].id, datetime.now(timezone.utc)
    )
    assert price == Decimal("161.0000")
