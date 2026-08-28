"""Tests for the deterministic 'why did my portfolio move?' explainer."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services import bootstrap
from app.services.explain import explain_move
from app.services.prices import ingest_bars
from app.services.valuation import take_snapshot

D1 = date(2026, 8, 24)
D2 = date(2026, 8, 25)


def _portfolio_with_two_holdings(client, db_session):
    user = bootstrap.create_user(db_session, email="a@b.com", display_name="T")
    bootstrap.create_instrument(db_session, symbol="AAPL", name="Apple", currency="CAD", sector="Tech")
    bootstrap.create_instrument(db_session, symbol="SHOP", name="Shopify", currency="CAD", sector="Tech")
    pf = bootstrap.create_portfolio(db_session, user_id=user.id, name="P", base_currency="CAD")
    bootstrap.fund_portfolio(db_session, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD")
    for sym, px in [("AAPL", 150), ("SHOP", 50)]:
        client.post(
            f"/portfolios/{pf.id}/orders",
            json={"side": "BUY", "symbol": sym, "quantity": 100, "price": px, "fee": 0},
            headers={"Idempotency-Key": f"{sym}"},
        )
    return pf


def _snapshot_two_days(db_session, pf):
    base = datetime.now(timezone.utc) - timedelta(days=10)
    # Day 1: AAPL 150, SHOP 50.
    ingest_bars(db_session, symbol="AAPL", bars=[(D1, Decimal("150"))], as_of=base)
    ingest_bars(db_session, symbol="SHOP", bars=[(D1, Decimal("50"))], as_of=base)
    take_snapshot(db_session, pf.id, "CAD", D1, as_of=base)
    # Day 2: AAPL +10 (up), SHOP -10 (down) -> net portfolio move ~0.
    t2 = base + timedelta(days=1)
    ingest_bars(db_session, symbol="AAPL", bars=[(D2, Decimal("160"))], as_of=t2)
    ingest_bars(db_session, symbol="SHOP", bars=[(D2, Decimal("40"))], as_of=t2)
    take_snapshot(db_session, pf.id, "CAD", D2, as_of=t2)


def test_contributions_reconcile_to_portfolio_return(client, db_session):
    pf = _portfolio_with_two_holdings(client, db_session)
    _snapshot_two_days(db_session, pf)

    e = explain_move(db_session, pf.id)
    assert e.available
    # AAPL +$1000, SHOP -$1000 => net move ~0.
    assert abs(e.portfolio_return) < 1e-9
    total = sum(d.contribution for d in e.drivers)
    assert abs(total - e.portfolio_return) < 1e-9  # decomposition reconciles

    by_symbol = {d.symbol: d for d in e.drivers}
    assert abs(by_symbol["AAPL"].contribution - 0.01) < 1e-9  # +1000/100000
    assert abs(by_symbol["SHOP"].contribution + 0.01) < 1e-9  # -1000/100000


def test_signals_attach_to_drivers_in_window(client, db_session):
    pf = _portfolio_with_two_holdings(client, db_session)
    _snapshot_two_days(db_session, pf)

    from app.models import Instrument

    aapl_id = db_session.query(Instrument).filter_by(symbol="AAPL").one().id
    bootstrap.create_signal(
        db_session,
        instrument_id=aapl_id,
        ts=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
        source="news",
        signal_type="sentiment",
        value=0.6,
        confidence=0.7,
        headline="Apple pops on upgrade",
        source_url="https://example.com/aapl",
    )

    e = explain_move(db_session, pf.id)
    by_symbol = {d.symbol: d for d in e.drivers}
    assert len(by_symbol["AAPL"].signals) == 1
    assert by_symbol["AAPL"].signals[0].headline == "Apple pops on upgrade"
    assert len(by_symbol["SHOP"].signals) == 0  # no signal for SHOP


def test_explain_unavailable_without_two_snapshots(client, db_session):
    pf = _portfolio_with_two_holdings(client, db_session)
    e = explain_move(db_session, pf.id)
    assert not e.available
    assert "two" in (e.reason or "")
