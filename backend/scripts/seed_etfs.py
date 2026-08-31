"""Create and backfill player-index ETFs from the seeded players.

Run AFTER players are seeded + backfilled.
    DATABASE_URL=... python -m scripts.seed_etfs
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Instrument
from app.services.etf import backfill_etf, define_etf


def _players(db, sport):
    return list(
        db.scalars(
            select(Instrument)
            .where(Instrument.asset_class == "PLAYER", Instrument.sport == sport)
            .order_by(Instrument.prior_value.desc().nullslast())
        )
    )


def main() -> None:
    db = SessionLocal()
    nba = _players(db, "NBA")
    nhl = _players(db, "NHL")

    defs = []
    if nba:
        defs.append(("NBAX", "NBA Index", "NBA", nba))
        defs.append(("NBATOP", "NBA Top 15", "NBA", nba[:15]))
    if nhl:
        defs.append(("NHLX", "NHL Index", "NHL", nhl))
        defs.append(("NHLTOP", "NHL Top 15", "NHL", nhl[:15]))
    if nba and nhl:
        defs.append(("ALLSTAR", "Two-Sport All-Stars", "MULTI", nba[:8] + nhl[:8]))
    # Rookie index: players whose prior came from a position prior (no prior season).
    rookies = [
        p for p in (nba + nhl)
        if (p.prior_basis or "").startswith("POS:")
    ][:20]
    if rookies:
        defs.append(("ROOKIE", "Rookie Index", "MULTI", rookies))
    # A team index example.
    for sport, players, sym, nm in [("NBA", nba, "LALX", "Lakers Index"), ("NHL", nhl, "EDMX", "Oilers Index")]:
        team_players = [p for p in players if p.team and (nm.split()[0] in p.team)]
        if len(team_players) >= 3:
            defs.append((sym, nm, sport, team_players))

    for symbol, name, sport, members in defs:
        etf = define_etf(db, symbol=symbol, name=name, sport=sport, members=members)
        bars = backfill_etf(db, etf)
        print(f"  {name:22} ({len(members)} players) -> {bars} price points")

    db.close()
    print(f"Seeded {len(defs)} ETFs.")


if __name__ == "__main__":
    main()
