"""Create demo portfolios that trade players, then snapshot them across the season.

Run AFTER seeding + backfilling players (NBA and/or NHL). Builds a few themed
rosters, buys at each player's earliest price, and snapshots point-in-time so the
leaderboard shows real player-portfolio competition with equity curves.

    DATABASE_URL=... python -m scripts.seed_portfolios
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, text

from app.db import SessionLocal
from app.models import Instrument, PriceBar
from app.services import bootstrap
from app.services.orders import place_order
from app.services.valuation import take_snapshot

DEMO_EMAIL = "demo@draftfolio.io"


def _earliest_bar(db, inst_id):
    return db.scalar(
        select(PriceBar)
        .where(PriceBar.instrument_id == inst_id, PriceBar.source == "espn")
        .order_by(PriceBar.bar_date.asc())
        .limit(1)
    )


def _players(db, sport, n):
    rows = db.scalars(
        select(Instrument)
        .where(Instrument.asset_class == "PLAYER", Instrument.sport == sport)
        .order_by(Instrument.prior_value.desc().nullslast())
    ).all()
    return rows[:n]


def main() -> None:
    db = SessionLocal()
    # wipe existing portfolios/ledger (keep instruments + price history)
    for t in ["portfolio_snapshots", "transactions", "orders", "positions", "cash_balances", "portfolios"]:
        db.execute(text(f"DELETE FROM {t}"))
    db.commit()

    user = db.scalar(select(bootstrap.User).where(bootstrap.User.email == DEMO_EMAIL))
    if user is None:
        user = bootstrap.create_user(db, email=DEMO_EMAIL, display_name="Demo User")

    nba = _players(db, "NBA", 8)
    nhl = _players(db, "NHL", 8)
    rosters = {
        "Hardwood Holdings": nba[:5],
        "Slapshot Syndicate": nhl[:5],
        "Two-Sport Fund": (nba[:3] + nhl[:3]),
        "Value Bench": (nba[5:8] + nhl[5:8]),
    }

    from datetime import datetime, timezone

    for name, players in rosters.items():
        players = [p for p in players if p is not None]
        if not players:
            continue
        pf = bootstrap.create_portfolio(db, user_id=user.id, name=name, base_currency="CAD")
        bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD")
        budget_each = Decimal("90000") / Decimal(len(players))  # headroom under the cap

        firsts: list = []
        lasts: list = []
        for p in players:
            bar = _earliest_bar(db, p.id)
            if bar is None or float(bar.close) <= 0:
                continue
            qty = (budget_each / Decimal(str(bar.close))).quantize(Decimal("1"))
            if qty <= 0:
                continue
            try:
                place_order(
                    db, portfolio_id=pf.id, idempotency_key=f"{pf.id}-{p.symbol}",
                    side="BUY", symbol=p.symbol, quantity=qty, price=Decimal(str(bar.close)),
                    currency="CAD", fee=Decimal("0"),
                )
            except Exception as e:  # noqa: BLE001 — skip a pick that won't fit
                print(f"    skip {p.symbol}: {e}")
                continue
            dates_p = [
                b.bar_date
                for b in db.scalars(
                    select(PriceBar).where(PriceBar.instrument_id == p.id, PriceBar.source == "espn")
                )
            ]
            if dates_p:
                firsts.append(min(dates_p))
                lasts.append(max(dates_p))

        # Snapshot from when ALL of this portfolio's holdings are priced (so no
        # holding is missing early) to the latest game; latest_close carries a
        # player's value forward between games.
        if firsts:
            start, end = max(firsts), max(lasts)
            span = (end - start).days
            if span > 0:
                n = 14
                for i in range(n + 1):
                    d = start + timedelta(days=round(i * span / n))
                    as_of = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
                    take_snapshot(db, pf.id, "CAD", d, as_of=as_of)
        print(f"  {name}: {len(players)} players")

    db.commit()
    db.close()
    print(f"Seeded {len(rosters)} demo portfolios.")


if __name__ == "__main__":
    main()
