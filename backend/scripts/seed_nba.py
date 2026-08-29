"""Seed the player market with real NBA players from ESPN.

Pulls rosters for a set of teams, computes each player's value from their season
averages, and creates a PLAYER instrument + today's price bar. Prices are in the
sim's virtual currency (CAD) so players draft alongside everything else with no
FX friction.

    DATABASE_URL=... python -m scripts.seed_nba              # marquee teams
    DATABASE_URL=... NBA_TEAMS=all python -m scripts.seed_nba  # all 30 teams

Idempotent: re-running updates existing players (matched on ESPN id) and today's
price rather than duplicating.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.domain.player_value import value_index
from app.models import Instrument, PriceBar
from app.services import nba_espn

CURRENCY = "CAD"  # virtual sim currency


def _upsert_player(db, meta: nba_espn.PlayerMeta, value: float) -> Instrument:
    symbol = f"NBA:{meta.espn_id}"
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if inst is None:
        inst = Instrument(symbol=symbol, currency=CURRENCY, asset_class="PLAYER")
        db.add(inst)
    inst.name = meta.name
    inst.sport = "NBA"
    inst.team = meta.team
    inst.position = meta.position
    inst.sector = meta.position  # reuse sector slot so existing UI groups by position
    inst.external_ref = meta.espn_id
    inst.headshot_url = meta.headshot_url
    db.flush()

    today = date.today()
    now = datetime.now(timezone.utc)
    bar = db.scalar(
        select(PriceBar).where(
            PriceBar.instrument_id == inst.id,
            PriceBar.bar_date == today,
            PriceBar.source == "nba_espn",
        )
    )
    if bar is None:
        bar = PriceBar(
            instrument_id=inst.id, bar_date=today, currency=CURRENCY, source="nba_espn"
        )
        db.add(bar)
    bar.close = Decimal(str(value))
    bar.as_of = now
    return inst


def main() -> None:
    which = os.getenv("NBA_TEAMS", "marquee").lower()
    if which == "all":
        team_ids = nba_espn.get_team_ids()
    else:
        team_ids = nba_espn.MARQUEE_TEAMS

    db = SessionLocal()
    seeded = 0
    for tid in team_ids:
        try:
            roster = nba_espn.get_roster(tid)
        except Exception as e:  # noqa: BLE001
            print(f"  team {tid}: roster error {e}")
            continue
        for meta in roster:
            stats = nba_espn.get_season_averages(meta.espn_id)
            if stats is None:
                continue  # no stats yet (two-way / rookie preseason) — skip
            value = value_index(stats, available=not meta.injured)
            inst = _upsert_player(db, meta, value)
            seeded += 1
            print(f"  {inst.name:24} {meta.team:22} {meta.position or '?':3} ${value}")
            time.sleep(0.05)  # be polite to ESPN
        db.commit()

    db.close()
    print(f"Seeded {seeded} NBA players across {len(team_ids)} teams.")


if __name__ == "__main__":
    main()
