"""Seed demo rival users (each with one team) and run a few gameweeks.

Populates the Bronze division so a fresh signup lands in a live ladder.
    DATABASE_URL=... python -m scripts.seed_rivals
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, text

from app.db import SessionLocal
from app.models import Instrument, PriceBar, User
from app.services import auth as auth_svc
from app.services import bootstrap
from app.services.orders import place_order
from app.services.rivals import run_gameweek

USERNAMES = ["frost", "blizzard", "slapshot", "hattrick", "gretzky99", "iceman", "puckluck", "topshelf"]


def _players(db, sport, n):
    return list(
        db.scalars(
            select(Instrument)
            .where(Instrument.asset_class == "PLAYER", Instrument.sport == sport)
            .order_by(Instrument.prior_value.desc().nullslast())
        )
    )[:n]


def _earliest_bar(db, iid):
    return db.scalar(
        select(PriceBar).where(PriceBar.instrument_id == iid, PriceBar.source == "espn")
        .order_by(PriceBar.bar_date.asc()).limit(1)
    )


def main() -> None:
    db = SessionLocal()
    # clean any prior rival users
    for uname in USERNAMES:
        u = db.scalar(select(User).where(User.username == uname))
        if u:
            for t in ["gameweek_results", "transactions", "orders", "positions", "cash_balances", "portfolio_snapshots"]:
                col = "user_id" if t == "gameweek_results" else "portfolio_id"
                if t == "gameweek_results":
                    db.execute(text("DELETE FROM gameweek_results WHERE user_id=:u"), {"u": u.id})
                else:
                    db.execute(text(f"DELETE FROM {t} WHERE portfolio_id IN (SELECT id FROM portfolios WHERE user_id=:u)"), {"u": u.id})
            db.execute(text("DELETE FROM portfolios WHERE user_id=:u"), {"u": u.id})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": u.id})
    db.execute(text("DELETE FROM gameweeks"))
    db.commit()

    nba = _players(db, "NBA", 20)
    nhl = _players(db, "NHL", 20)
    pool = nba + nhl

    for i, uname in enumerate(USERNAMES):
        user = User(
            email=f"{uname}@rivals.io", display_name=uname, username=uname,
            password_hash=auth_svc.hash_password("password"), division="Bronze",
        )
        db.add(user)
        db.commit()
        pf = bootstrap.create_portfolio(db, user_id=user.id, name=f"{uname}'s Team")
        bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("100000"), currency="CAD")
        # each user drafts a rotating slice of 5 players
        picks = [pool[(i * 3 + k) % len(pool)] for k in range(5)]
        for p in picks:
            bar = _earliest_bar(db, p.id)
            if not bar:
                continue
            qty = (Decimal("18000") / Decimal(str(bar.close))).quantize(Decimal("1"))
            if qty <= 0:
                continue
            try:
                place_order(db, portfolio_id=pf.id, idempotency_key=f"{pf.id}-{p.symbol}",
                            side="BUY", symbol=p.symbol, quantity=qty, price=Decimal(str(bar.close)),
                            currency="CAD", fee=Decimal("0"))
            except Exception:  # noqa: BLE001
                pass
        print(f"  {uname}: team ready")

    # Run 3 gameweeks across the season.
    windows = [
        (date(2025, 12, 1), date(2025, 12, 15)),
        (date(2026, 1, 15), date(2026, 2, 1)),
        (date(2026, 3, 1), date(2026, 3, 20)),
    ]
    for n, (s, e) in enumerate(windows, start=1):
        out = run_gameweek(db, number=n, start=s, end=e)
        print(f"  gameweek {n}: scored {out.scored} teams")

    db.close()
    print(f"Seeded {len(USERNAMES)} rivals + {len(windows)} gameweeks.")


if __name__ == "__main__":
    main()
