"""Backfill price history for seeded NBA players from ESPN game logs.

    DATABASE_URL=... python -m scripts.backfill_nba            # all players
    DATABASE_URL=... NBA_BACKFILL_LIMIT=20 python -m scripts.backfill_nba

Idempotent: re-running updates raw games + recomputes prices in place. Resilient:
one bad player is logged and skipped, never aborts the whole run.
"""

from __future__ import annotations

import os
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Instrument
from app.services import nba_espn
from app.services.nba_backfill import backfill_player


def main() -> None:
    limit = int(os.getenv("NBA_BACKFILL_LIMIT", "0")) or None
    db = SessionLocal()
    players = list(
        db.scalars(
            select(Instrument)
            .where(Instrument.asset_class == "PLAYER", Instrument.sport == "NBA")
            .order_by(Instrument.name)
        )
    )
    if limit:
        players = players[:limit]

    done = 0
    failed = 0
    for inst in players:
        try:
            games = nba_espn.get_gamelog(inst.external_ref)
            bars = backfill_player(db, inst, games)
        except Exception as e:  # noqa: BLE001 — one bad player must not kill the job
            db.rollback()
            failed += 1
            print(f"  {inst.name:24} SKIPPED ({type(e).__name__}: {e})")
            continue
        done += 1
        print(f"  {inst.name:24} {bars} price points")
        time.sleep(0.05)

    db.close()
    print(f"Backfilled {done} players ({failed} skipped).")


if __name__ == "__main__":
    main()
