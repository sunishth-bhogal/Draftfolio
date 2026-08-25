"""Integration tests: HTTP -> service -> domain -> DB, incl. reconciliation."""

from __future__ import annotations

from decimal import Decimal

from app.services.reconcile import reconcile


def _order_body(**over):
    body = {"side": "BUY", "symbol": "AAPL", "quantity": 10, "price": 150, "fee": 1}
    body.update(over)
    return body


def test_place_buy_order_updates_state(client, seeded):
    pf_id = str(seeded["portfolio"].id)
    r = client.post(
        f"/portfolios/{pf_id}/orders",
        json=_order_body(),
        headers={"Idempotency-Key": "k1"},
    )
    assert r.status_code == 201, r.text

    state = client.get(f"/portfolios/{pf_id}").json()
    # 100000 - (10 * 150) - 1 fee = 98499
    cash = {c["currency"]: Decimal(c["amount"]) for c in state["cash"]}
    assert cash["CAD"] == Decimal("98499.0000")
    positions = {p["symbol"]: Decimal(p["quantity"]) for p in state["positions"]}
    assert positions["AAPL"] == Decimal("10.00000000")


def test_idempotent_retry_creates_one_order(client, seeded):
    pf_id = str(seeded["portfolio"].id)
    headers = {"Idempotency-Key": "same-key"}

    r1 = client.post(f"/portfolios/{pf_id}/orders", json=_order_body(), headers=headers)
    r2 = client.post(f"/portfolios/{pf_id}/orders", json=_order_body(), headers=headers)

    assert r1.status_code == 201  # created
    assert r2.status_code == 200  # replay, not created
    assert r1.json()["id"] == r2.json()["id"]  # same order

    # Cash was debited exactly once.
    state = client.get(f"/portfolios/{pf_id}").json()
    cash = {c["currency"]: Decimal(c["amount"]) for c in state["cash"]}
    assert cash["CAD"] == Decimal("98499.0000")


def test_insufficient_cash_is_rejected(client, seeded):
    pf_id = str(seeded["portfolio"].id)
    r = client.post(
        f"/portfolios/{pf_id}/orders",
        json=_order_body(quantity=1000, price=500),  # 500k > 100k
        headers={"Idempotency-Key": "toobig"},
    )
    assert r.status_code == 422
    assert "need" in r.json()["detail"]


def test_cannot_oversell(client, seeded):
    pf_id = str(seeded["portfolio"].id)
    client.post(
        f"/portfolios/{pf_id}/orders",
        json=_order_body(side="BUY", quantity=5),
        headers={"Idempotency-Key": "buy5"},
    )
    r = client.post(
        f"/portfolios/{pf_id}/orders",
        json=_order_body(side="SELL", quantity=10),
        headers={"Idempotency-Key": "sell10"},
    )
    assert r.status_code == 422


def test_reconciliation_holds_after_trades(client, seeded, db_session):
    pf_id = seeded["portfolio"].id
    for i, (side, qty) in enumerate([("BUY", 10), ("BUY", 5), ("SELL", 8)]):
        client.post(
            f"/portfolios/{pf_id}/orders",
            json=_order_body(side=side, quantity=qty),
            headers={"Idempotency-Key": f"o{i}"},
        )

    result = reconcile(db_session, pf_id)
    assert result.ok, result.discrepancies
