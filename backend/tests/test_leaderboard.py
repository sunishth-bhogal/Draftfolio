"""End-to-end leaderboard: two portfolios, scored and ranked over the API."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services import bootstrap
from app.services.prices import ingest_bars
from app.services.valuation import take_snapshot

DATES = [date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 24)]


def _snapshots(db, pf, marks, as_of_base):
    for i, (d, c) in enumerate(zip(DATES, marks)):
        as_of = as_of_base + timedelta(days=i)
        ingest_bars(db, symbol="AAPL", bars=[(d, Decimal(str(c)))], as_of=as_of)
        take_snapshot(db, pf.id, "CAD", d, as_of=as_of)


def test_leaderboard_ranks_all_portfolios(client, seeded, db_session):
    pf1 = seeded["portfolio"]
    user = seeded["user"]
    pf2 = bootstrap.create_portfolio(
        db_session, user_id=user.id, name="Second", base_currency="CAD"
    )
    bootstrap.fund_portfolio(
        db_session, portfolio_id=pf2.id, amount=Decimal("100000"), currency="CAD"
    )

    # Both buy AAPL; they share the same price path here (enough to exercise ranking).
    for pf in (pf1, pf2):
        client.post(
            f"/portfolios/{pf.id}/orders",
            json={"side": "BUY", "symbol": "AAPL", "quantity": 10, "price": 150, "fee": 0},
            headers={"Idempotency-Key": f"buy-{pf.id}"},
        )

    base = datetime.now(timezone.utc) - timedelta(days=10)
    _snapshots(db_session, pf1, [150, 156, 150], base)
    _snapshots(db_session, pf2, [150, 156, 150], base)

    lb = client.get("/leaderboard", params={"mode": "BALANCED"}).json()

    assert lb["mode"] == "BALANCED"
    assert abs(sum(lb["weights"].values()) - 1.0) < 1e-9  # weights are a real convex combo
    assert len(lb["rows"]) == 2
    assert {r["rank"] for r in lb["rows"]} == {1, 2}  # distinct ranks assigned
    for r in lb["rows"]:
        assert 0.0 <= r["score"] <= 100.0
        assert set(r["percentiles"]) == {"R", "B", "D", "C"}


def test_leaderboard_modes_expose_weights(client, seeded):
    for mode, expect_R in [("SPRINT", 0.85), ("INVESTOR", 0.30)]:
        lb = client.get("/leaderboard", params={"mode": mode}).json()
        assert lb["weights"]["R"] == expect_R
