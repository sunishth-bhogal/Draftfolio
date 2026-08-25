"""Populate the DB with demo data so the frontend has something to show.

Creates a few instruments and three portfolios with distinct strategies, a ~12
day price history, orders, and daily snapshots — enough to exercise valuation,
analytics, and the leaderboard. Idempotent-ish: wipes existing rows first.

Run:  DATABASE_URL=postgresql+psycopg://... python -m scripts.seed_demo
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.db import SessionLocal
from app.services import bootstrap
from app.services.orders import place_order
from app.services.prices import ingest_bars
from app.services.valuation import take_snapshot

TABLES = [
    "portfolio_snapshots", "transactions", "orders", "price_bars",
    "positions", "cash_balances", "portfolios", "instruments", "users",
]

# 12 business-ish days of closes per symbol.
DATES = [date(2026, 8, 10) + timedelta(days=i) for i in range(12)]
PRICES = {
    "AAPL": [150, 152, 149, 155, 160, 158, 163, 159, 165, 168, 164, 170],
    "XEQT": [30.0, 30.2, 30.1, 30.4, 30.6, 30.5, 30.7, 30.6, 30.9, 31.0, 30.8, 31.2],
    "SHOP": [70, 74, 68, 80, 92, 85, 60, 78, 95, 88, 72, 99],   # volatile
    "ENB":  [48, 48.2, 48.1, 48.3, 48.5, 48.4, 48.6, 48.7, 48.5, 48.8, 48.9, 49.0],  # steady
}
META = {
    "AAPL": ("Apple Inc.", "Technology"),
    "XEQT": ("iShares All-Equity ETF", "ETF"),
    "SHOP": ("Shopify Inc.", "Technology"),
    "ENB": ("Enbridge Inc.", "Energy"),
}


def wipe(db):
    for t in TABLES:
        db.execute(text(f"DELETE FROM {t}"))
    db.commit()


def main():
    db = SessionLocal()
    wipe(db)

    user = bootstrap.create_user(db, email="demo@draftfolio.io", display_name="Demo User")
    for sym, (name, sector) in META.items():
        bootstrap.create_instrument(db, symbol=sym, name=name, currency="CAD", sector=sector)

    # Six strategies spanning the risk/return/diversification space, so the
    # percentile-ranked leaderboard has a real field to differentiate.
    strategies = {
        "Power Play (Volatile)": [("SHOP", 900)],
        "Blue Line (Tech)": [("AAPL", 300), ("SHOP", 200)],
        "Balanced Attack": [("AAPL", 150), ("XEQT", 1500), ("ENB", 400)],
        "Two-Way Threat": [("AAPL", 200), ("ENB", 300), ("XEQT", 800)],
        "The Grinder": [("ENB", 2000)],
        "Rookie Run": [("AAPL", 400), ("SHOP", 400)],
    }

    portfolios = []
    for name, holdings in strategies.items():
        pf = bootstrap.create_portfolio(db, user_id=user.id, name=name, base_currency="CAD")
        bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD")
        for i, (sym, qty) in enumerate(holdings):
            place_order(
                db,
                portfolio_id=pf.id,
                idempotency_key=f"{pf.id}-{sym}",
                side="BUY",
                symbol=sym,
                quantity=Decimal(qty),
                price=Decimal(str(PRICES[sym][0])),
                currency="CAD",
                fee=Decimal("0"),
            )
        portfolios.append(pf)

    # Walk the price history forward, snapshotting each day point-in-time.
    base = datetime.now(timezone.utc) - timedelta(days=30)
    for day_i, d in enumerate(DATES):
        as_of = base + timedelta(days=day_i)
        for sym, series in PRICES.items():
            ingest_bars(db, symbol=sym, bars=[(d, Decimal(str(series[day_i])))], as_of=as_of)
        for pf in portfolios:
            take_snapshot(db, pf.id, "CAD", d, as_of=as_of)

    db.close()
    print(f"Seeded {len(portfolios)} portfolios, {len(META)} instruments, {len(DATES)} days.")


if __name__ == "__main__":
    main()
