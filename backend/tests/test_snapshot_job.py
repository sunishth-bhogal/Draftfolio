"""Tests for the daily snapshot worker."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.services import bootstrap
from app.services.prices import ingest_bars
from app.services.snapshot_job import run_daily_snapshots
from app.services.valuation import return_series


def _setup(db):
    user = bootstrap.create_user(db, email="a@b.com", display_name="T")
    bootstrap.create_instrument(db, symbol="AAPL", name="Apple", currency="CAD", sector="Tech")
    pf = bootstrap.create_portfolio(db, user_id=user.id, name="P", base_currency="CAD")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD")
    return pf


def test_job_snapshots_all_portfolios(client, db_session):
    pf = _setup(db_session)
    client.post(
        f"/portfolios/{pf.id}/orders",
        json={"side": "BUY", "symbol": "AAPL", "quantity": 100, "price": 150, "fee": 0},
        headers={"Idempotency-Key": "b1"},
    )
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 24), Decimal("150"))])

    result = run_daily_snapshots(db_session, as_of_date=date(2026, 8, 25))
    assert result.snapshots_written == 1
    # AAPL had no bar on the 25th; the job carried forward the 24th's mark.
    assert result.prices_carried_forward == 1

    series = return_series(db_session, pf.id)
    assert len(series) == 1
    assert series[0].snapshot_date == date(2026, 8, 25)


def test_job_accrues_history_over_days(client, db_session):
    pf = _setup(db_session)
    client.post(
        f"/portfolios/{pf.id}/orders",
        json={"side": "BUY", "symbol": "AAPL", "quantity": 100, "price": 150, "fee": 0},
        headers={"Idempotency-Key": "b1"},
    )
    # Day 1 mark 150, day 2 mark 160 (10 shares * ... 100 shares).
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 24), Decimal("150"))])
    run_daily_snapshots(db_session, as_of_date=date(2026, 8, 24))
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 25), Decimal("160"))])
    run_daily_snapshots(db_session, as_of_date=date(2026, 8, 25))

    series = return_series(db_session, pf.id)
    assert len(series) == 2
    # equity: day1 = 85000 cash + 100*150 = 100000; day2 = 85000 + 100*160 = 101000
    assert series[0].equity == Decimal("100000.0000")
    assert series[1].equity == Decimal("101000.0000")
    assert series[1].daily_return == Decimal("0.010000")  # +1%


def test_job_is_idempotent(client, db_session):
    pf = _setup(db_session)
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 24), Decimal("150"))])

    run_daily_snapshots(db_session, as_of_date=date(2026, 8, 25))
    run_daily_snapshots(db_session, as_of_date=date(2026, 8, 25))  # rerun same day

    series = return_series(db_session, pf.id)
    assert len(series) == 1  # one snapshot for the date, not two
