"""Seed the player market with real NHL skaters from ESPN (model v2).

Mirrors seed_nba: derives a current-season observed value and a v2 prior
(previous-season value for veterans; a position-based league prior for rookies).
Prices come from the game-log backfill (run backfill_nhl afterward).

    DATABASE_URL=... python -m scripts.seed_nhl
    DATABASE_URL=... NHL_TEAMS=all python -m scripts.seed_nhl
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from sqlalchemy import select

from app.db import SessionLocal
from app.domain.player_value import FORMULA_VERSION, shrink, value_from_production
from app.domain.sports import NHL, production_from_stats
from app.models import Instrument
from app.services import nhl_espn

CURRENCY = "CAD"


def _upsert(db, meta: nhl_espn.PlayerMeta) -> Instrument:
    symbol = f"NHL:{meta.espn_id}"
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if inst is None:
        inst = Instrument(symbol=symbol, currency=CURRENCY, asset_class="PLAYER")
        db.add(inst)
    inst.name = meta.name
    inst.sport = "NHL"
    inst.team = meta.team
    inst.position = meta.position
    inst.sector = meta.position
    inst.external_ref = meta.espn_id
    inst.headshot_url = meta.headshot_url
    inst.injury_status = meta.injury_status
    db.flush()
    return inst


def main() -> None:
    which = os.getenv("NHL_TEAMS", "marquee").lower()
    team_ids = nhl_espn.get_team_ids() if which == "all" else nhl_espn.MARQUEE_TEAMS

    db = SessionLocal()
    info: list[tuple[Instrument, int, str | None]] = []
    for tid in team_ids:
        try:
            roster = nhl_espn.get_roster(tid)
        except Exception as e:  # noqa: BLE001
            print(f"  team {tid}: {e}")
            continue
        for meta in roster:
            hist = nhl_espn.get_season_history(meta.espn_id)
            if not hist:
                continue
            _name, current, games = hist[0]
            inst = _upsert(db, meta)
            if len(hist) > 1:
                inst.prior_value = value_from_production(
                    production_from_stats("NHL", hist[1][1]), NHL.scale
                )
                inst.prior_basis = hist[1][0]
            else:
                inst.prior_value = None
                inst.prior_basis = None
            db.flush()
            info.append((inst, games, meta.position))
            time.sleep(0.03)
        db.commit()

    pos_vals: dict[str, list[float]] = defaultdict(list)
    all_priors = [i.prior_value for i, *_ in info if i.prior_value is not None]
    league_prior = round(sum(all_priors) / len(all_priors), 2) if all_priors else 100.0
    for inst, _g, pos in info:
        if inst.prior_value is not None and pos:
            pos_vals[pos].append(inst.prior_value)
    pos_prior = {p: round(sum(v) / len(v), 2) for p, v in pos_vals.items()}

    for inst, games, pos in info:
        if inst.prior_value is None:
            inst.prior_value = pos_prior.get(pos, league_prior)
            inst.prior_basis = f"POS:{pos or 'NHL'} prior"
        print(f"  {inst.name:22} {inst.position or '?':3} prior=${inst.prior_value} g={games}")
    db.commit()
    db.close()
    print(f"Seeded {len(info)} NHL skaters (model {FORMULA_VERSION}). Run backfill_nhl for prices.")


if __name__ == "__main__":
    main()
