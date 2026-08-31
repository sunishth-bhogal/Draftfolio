"""Sport-agnostic price-history backfill.

Given a player's per-game observations (each with a raw ``stats`` dict), stores
them and reconstructs a point-in-time v2 value series: at each game date, value
from season-to-date mean production × the sport's scale, adjusted for form and
shrunk toward the player's prior. Works for any sport in ``domain.sports``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.player_value import FORMULA_VERSION, form_multiplier, shrink, value_from_production
from app.domain.sports import SPORTS, production_from_stats
from app.models import Instrument, PlayerGame, PriceBar

FORM_WINDOW = 5


@dataclass
class GenericGame:
    espn_event_id: str
    game_date: date
    opponent: str | None
    home: bool
    minutes: float
    stats: dict[str, float]


def _store_game(db: Session, inst: Instrument, g: GenericGame, production: float) -> None:
    existing = db.scalar(
        select(PlayerGame).where(
            PlayerGame.instrument_id == inst.id,
            PlayerGame.espn_event_id == g.espn_event_id,
        )
    )
    row = existing or PlayerGame(instrument_id=inst.id, espn_event_id=g.espn_event_id)
    row.game_date = g.game_date
    row.opponent = g.opponent
    row.home = g.home
    row.minutes = g.minutes
    row.stats_json = json.dumps(g.stats)
    row.production = production
    # Mirror NBA stats into typed columns for back-compat with existing NBA code.
    for col in ("points", "rebounds", "assists", "steals", "blocks", "turnovers"):
        if col in g.stats:
            setattr(row, col, g.stats[col])
    if existing is None:
        db.add(row)


def _mean_production(productions: list[float]) -> float:
    return sum(productions) / len(productions) if productions else 0.0


def backfill_player_generic(
    db: Session, instrument: Instrument, games: list[GenericGame], sport: str
) -> int:
    if not games:
        return 0
    seen: set[str] = set()
    games = [
        g for g in sorted(games, key=lambda g: g.game_date)
        if not (g.espn_event_id in seen or seen.add(g.espn_event_id))
    ]
    scale = SPORTS[sport].scale
    prods = [production_from_stats(sport, g.stats) for g in games]
    for g, p in zip(games, prods):
        _store_game(db, instrument, g, p)

    prior = float(instrument.prior_value) if instrument.prior_value is not None else None
    bars = 0
    for i in range(len(games)):
        season = prods[: i + 1]
        recent = prods[max(0, i + 1 - FORM_WINDOW) : i + 1]
        form = form_multiplier(sum(recent) / len(recent), sum(season) / len(season))
        observed = value_from_production(_mean_production(season), scale, form_multiplier=form)
        p = prior if prior is not None else observed
        value = shrink(observed, p, games=i + 1)
        _write_price(db, instrument, games[i].game_date, value)
        bars += 1

    from app.services.catalysts import write_catalyst_signal

    write_catalyst_signal(db, instrument)
    db.commit()
    return bars


def _write_price(db: Session, inst: Instrument, bar_date: date, value: float) -> None:
    existing = db.scalar(
        select(PriceBar).where(
            PriceBar.instrument_id == inst.id,
            PriceBar.bar_date == bar_date,
            PriceBar.source == "espn",
        )
    )
    bar = existing or PriceBar(instrument_id=inst.id, bar_date=bar_date, source="espn")
    bar.close = Decimal(str(value))
    bar.currency = inst.currency
    bar.formula_version = FORMULA_VERSION
    bar.as_of = datetime.combine(
        bar_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )
    if existing is None:
        db.add(bar)
    # Flush so a same-date lookup later this run finds it (updates in place)
    # instead of inserting a duplicate — the session is autoflush=False.
    db.flush()
