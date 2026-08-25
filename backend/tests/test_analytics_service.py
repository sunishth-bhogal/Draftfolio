"""End-to-end analytics: build a snapshot history + benchmark, hit the API."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services import bootstrap
from app.services.prices import ingest_bars
from app.services.valuation import take_snapshot

# A four-day AAPL path and a correlated benchmark on the same dates.
DATES = [date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 24), date(2026, 8, 25)]
AAPL = [Decimal("150"), Decimal("153"), Decimal("150"), Decimal("156")]
XEQT = [Decimal("30.00"), Decimal("30.30"), Decimal("30.00"), Decimal("30.60")]


def _build_history(db, pf):
    base = datetime.now(timezone.utc) - timedelta(days=10)
    # Benchmark bars available up front.
    bootstrap.create_instrument(db, symbol="XEQT", name="iShares All-Eq", currency="CAD")
    for d, c in zip(DATES, XEQT):
        ingest_bars(db, symbol="XEQT", bars=[(d, c)], source="seed")
    # AAPL: ingest each day with an increasing as_of, snapshot as of that time,
    # so each snapshot reflects only prices known by then (point-in-time).
    for i, (d, c) in enumerate(zip(DATES, AAPL)):
        as_of = base + timedelta(days=i)
        ingest_bars(db, symbol="AAPL", bars=[(d, c)], source="seed", as_of=as_of)
        take_snapshot(db, pf.id, "CAD", d, as_of=as_of)


def test_analytics_endpoint(client, seeded, db_session):
    pf = seeded["portfolio"]
    # Buy 10 AAPL (fee 0) so equity moves purely with the AAPL mark.
    client.post(
        f"/portfolios/{pf.id}/orders",
        json={"side": "BUY", "symbol": "AAPL", "quantity": 10, "price": 150, "fee": 0},
        headers={"Idempotency-Key": "b1"},
    )
    _build_history(db_session, pf)

    a = client.get(f"/portfolios/{pf.id}/analytics", params={"benchmark": "XEQT", "rf": 0.04}).json()

    assert a["periods"] == 3  # 4 snapshots -> 3 returns
    assert a["annualized_volatility"] is not None and a["annualized_volatility"] > 0
    assert a["sharpe"] is not None
    assert a["max_drawdown"] is not None and a["max_drawdown"] > 0
    # benchmark-relative metrics populated
    assert a["benchmark"] == "XEQT"
    assert a["beta"] is not None
    assert a["alpha"] is not None
    assert a["tracking_error"] is not None
    # single holding => effective holdings ~ 1
    assert abs(a["effective_holdings"] - 1.0) < 1e-6
    assert abs(a["hhi"] - 1.0) < 1e-6


def test_analytics_without_snapshots_is_graceful(client, seeded):
    pf = seeded["portfolio"]
    a = client.get(f"/portfolios/{pf.id}/analytics").json()
    assert a["periods"] == 0
    assert a["sharpe"] is None
    assert any("snapshot" in n for n in a["notes"])
