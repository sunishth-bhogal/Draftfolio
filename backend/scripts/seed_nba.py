"""Seed the player market with real NBA players from ESPN (model v2).

For each player: fetch season history, derive a current-season observed value and
a v2 prior (previous-season value for veterans; a position-based league prior for
rookies), then write today's *reliability-shrunk* price.

    DATABASE_URL=... python -m scripts.seed_nba              # marquee teams
    DATABASE_URL=... NBA_TEAMS=all python -m scripts.seed_nba  # all 30 teams

Idempotent: matches players on ESPN id.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.domain.player_value import FORMULA_VERSION, shrink, value_index
from app.models import Instrument, PriceBar
from app.services import nba_espn

CURRENCY = "CAD"  # virtual sim currency


def _upsert_instrument(db, meta: nba_espn.PlayerMeta) -> Instrument:
    symbol = f"NBA:{meta.espn_id}"
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if inst is None:
        inst = Instrument(symbol=symbol, currency=CURRENCY, asset_class="PLAYER")
        db.add(inst)
    inst.name = meta.name
    inst.sport = "NBA"
    inst.team = meta.team
    inst.position = meta.position
    inst.sector = meta.position
    inst.external_ref = meta.espn_id
    inst.headshot_url = meta.headshot_url
    db.flush()
    return inst


def _write_price(db, inst: Instrument, value: float) -> None:
    today = date.today()
    bar = db.scalar(
        select(PriceBar).where(
            PriceBar.instrument_id == inst.id,
            PriceBar.bar_date == today,
            PriceBar.source == "nba_espn",
        )
    )
    if bar is None:
        bar = PriceBar(instrument_id=inst.id, bar_date=today, currency=CURRENCY, source="nba_espn")
        db.add(bar)
    bar.close = Decimal(str(value))
    bar.formula_version = FORMULA_VERSION
    bar.as_of = datetime.now(timezone.utc)


def main() -> None:
    which = os.getenv("NBA_TEAMS", "marquee").lower()
    team_ids = nba_espn.get_team_ids() if which == "all" else nba_espn.MARQUEE_TEAMS

    db = SessionLocal()
    # Pass 1: instruments + veteran priors + observed value.
    info: list[tuple[Instrument, float, int, str | None]] = []  # (inst, observed, games, pos)
    for tid in team_ids:
        try:
            roster = nba_espn.get_roster(tid)
        except Exception as e:  # noqa: BLE001
            print(f"  team {tid}: {e}")
            continue
        for meta in roster:
            hist = nba_espn.get_season_history(meta.espn_id)
            if not hist:
                continue
            current = hist[0][1]
            observed = value_index(current, available=not meta.injured)
            inst = _upsert_instrument(db, meta)
            if len(hist) > 1:  # veteran: previous season is the prior
                inst.prior_value = value_index(hist[1][1])
                inst.prior_basis = hist[1][0]
            else:
                inst.prior_value = None  # rookie: filled from position prior below
                inst.prior_basis = None
            db.flush()
            info.append((inst, observed, current.games, meta.position))
            time.sleep(0.03)
        db.commit()

    # Position priors (from veterans) for rookies who lack a previous season.
    pos_vals: dict[str, list[float]] = defaultdict(list)
    all_priors = [i.prior_value for i, *_ in info if i.prior_value is not None]
    league_prior = round(sum(all_priors) / len(all_priors), 2) if all_priors else 100.0
    for inst, _obs, _g, pos in info:
        if inst.prior_value is not None and pos:
            pos_vals[pos].append(inst.prior_value)
    pos_prior = {p: round(sum(v) / len(v), 2) for p, v in pos_vals.items()}

    # Pass 2: fill rookie priors and write v2 shrunk current prices.
    for inst, observed, games, pos in info:
        if inst.prior_value is None:
            inst.prior_value = pos_prior.get(pos, league_prior)
            inst.prior_basis = f"POS:{pos or 'NBA'} prior"
        adjusted = shrink(observed, inst.prior_value, games)
        _write_price(db, inst, adjusted)
        print(f"  {inst.name:24} {inst.position or '?':3} obs=${observed} prior=${inst.prior_value} g={games} -> ${adjusted}")
    db.commit()
    db.close()
    print(f"Seeded {len(info)} NBA players (model {FORMULA_VERSION}).")


if __name__ == "__main__":
    main()
