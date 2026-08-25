"""Tests for catalog + portfolio creation (the draft-room write path)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services import bootstrap
from app.services.prices import ingest_bars


def test_create_portfolio_funds_it(client):
    r = client.post("/portfolios", json={"name": "My Draft", "starting_cash": 100000})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    # It appears in the list and is funded.
    names = [p["name"] for p in client.get("/portfolios").json()]
    assert "My Draft" in names
    state = client.get(f"/portfolios/{pid}").json()
    cash = {c["currency"]: Decimal(c["amount"]) for c in state["cash"]}
    assert cash["CAD"] == Decimal("100000.0000")


def test_instruments_include_last_price(client, db_session):
    bootstrap.create_instrument(db_session, symbol="AAPL", name="Apple", currency="CAD", sector="Tech")
    ingest_bars(db_session, symbol="AAPL", bars=[(date(2026, 8, 25), Decimal("173.50"))])

    rows = client.get("/instruments").json()
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["last_price"] == 173.5
    assert aapl["sector"] == "Tech"


def test_draft_flow_create_then_buy(client, db_session):
    """Simulate the draft: create a portfolio, then place picks as orders."""
    pid = client.post("/portfolios", json={"name": "Rookie"}).json()["id"]
    bootstrap.create_instrument(db_session, symbol="AAPL", name="Apple", currency="CAD", sector="Tech")

    r = client.post(
        f"/portfolios/{pid}/orders",
        json={"side": "BUY", "symbol": "AAPL", "quantity": 100, "price": 150, "fee": 0},
        headers={"Idempotency-Key": f"{pid}-AAPL"},
    )
    assert r.status_code == 201
    state = client.get(f"/portfolios/{pid}").json()
    assert any(
        p["symbol"] == "AAPL" and Decimal(p["quantity"]) == Decimal("100")
        for p in state["positions"]
    )
