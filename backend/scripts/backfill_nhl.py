"""Backfill NHL skater price history from ESPN game logs."""

from __future__ import annotations

import os
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Instrument
from app.services import nhl_espn
from app.services.player_backfill import GenericGame, backfill_player_generic


def main() -> None:
    limit = int(os.getenv("NHL_BACKFILL_LIMIT", "0")) or None
    db = SessionLocal()
    players = list(
        db.scalars(
            select(Instrument)
            .where(Instrument.asset_class == "PLAYER", Instrument.sport == "NHL")
            .order_by(Instrument.name)
        )
    )
    if limit:
        players = players[:limit]

    done = failed = 0
    for inst in players:
        try:
            gl = nhl_espn.get_gamelog(inst.external_ref)
            games = [
                GenericGame(g.espn_event_id, g.game_date, g.opponent, g.home, g.minutes, g.stats)
                for g in gl
            ]
            bars = backfill_player_generic(db, inst, games, sport="NHL")
        except Exception as e:  # noqa: BLE001
            db.rollback(); failed += 1
            print(f"  {inst.name:22} SKIPPED ({type(e).__name__}: {e})")
            continue
        done += 1
        print(f"  {inst.name:22} {bars} price points")
        time.sleep(0.05)
    db.close()
    print(f"Backfilled {done} NHL players ({failed} skipped).")


if __name__ == "__main__":
    main()
