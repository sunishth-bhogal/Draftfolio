"""Player value explanation + model validation — makes the price legible.

Everything here is computed from the stored raw ``player_games`` (not a live
call), so a breakdown always reconciles to the same numbers and the model can be
audited offline.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.player_value import (
    FLOOR,
    FORMULA_VERSION,
    PlayerStats,
    form_multiplier,
    production_score,
    value_breakdown,
    value_index,
)
from app.models import Instrument, PlayerGame

FORM_WINDOW = 5


def _mean_stats(rows: list[PlayerGame]) -> PlayerStats:
    n = len(rows)
    if n == 0:
        return PlayerStats(0, 0, 0, 0, 0, 0, 0, 0)
    return PlayerStats(
        games=n,
        minutes=sum(r.minutes for r in rows) / n,
        points=sum(r.points for r in rows) / n,
        rebounds=sum(r.rebounds for r in rows) / n,
        assists=sum(r.assists for r in rows) / n,
        steals=sum(r.steals for r in rows) / n,
        blocks=sum(r.blocks for r in rows) / n,
        turnovers=sum(r.turnovers for r in rows) / n,
    )


@dataclass
class Breakdown:
    available: bool
    games: int = 0
    formula_version: str = FORMULA_VERSION
    averages: dict[str, float] = field(default_factory=dict)
    components: dict[str, float] = field(default_factory=dict)  # per-stat $ contribution
    base_value: float = 0.0
    form_multiplier: float = 1.0
    form_adjustment: float = 0.0
    final_value: float = 0.0


def value_breakdown_for(db: Session, instrument_id: uuid.UUID) -> Breakdown:
    rows = list(
        db.scalars(
            select(PlayerGame)
            .where(PlayerGame.instrument_id == instrument_id)
            .order_by(PlayerGame.game_date.asc())
        )
    )
    if not rows:
        return Breakdown(available=False)

    season = _mean_stats(rows)
    recent = _mean_stats(rows[-FORM_WINDOW:])
    form = form_multiplier(production_score(recent), production_score(season))

    base = round(max(FLOOR, production_score(season) * 12.0), 2)  # VALUE_SCALE
    final = value_index(season, form_multiplier=form)

    return Breakdown(
        available=True,
        games=len(rows),
        averages={
            "points": round(season.points, 1),
            "rebounds": round(season.rebounds, 1),
            "assists": round(season.assists, 1),
            "steals": round(season.steals, 1),
            "blocks": round(season.blocks, 1),
            "turnovers": round(season.turnovers, 1),
            "minutes": round(season.minutes, 1),
        },
        components=value_breakdown(season),
        base_value=base,
        form_multiplier=round(form, 3),
        form_adjustment=round(base * (form - 1.0), 2),
        final_value=final,
    )


# --- league-level validation -------------------------------------------------


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


@dataclass
class ValidationRow:
    name: str
    value: float
    ppg: float
    production: float
    games: int


@dataclass
class Validation:
    num_players: int
    corr_value_production: float | None
    corr_value_minutes: float | None
    min_games: int
    top: list[ValidationRow] = field(default_factory=list)  # reliable (>= min_games)
    watchouts: list[ValidationRow] = field(default_factory=list)  # high value, small sample


def league_validation(db: Session) -> Validation:
    players = db.scalars(
        select(Instrument).where(Instrument.asset_class == "PLAYER")
    ).all()

    values: list[float] = []
    prods: list[float] = []
    mins: list[float] = []
    rows: list[ValidationRow] = []
    for p in players:
        games = list(
            db.scalars(select(PlayerGame).where(PlayerGame.instrument_id == p.id))
        )
        if not games:
            continue
        s = _mean_stats(games)
        prod = production_score(s)
        val = value_index(s)
        values.append(val)
        prods.append(prod)
        mins.append(s.minutes)
        rows.append(ValidationRow(p.name, val, round(s.points, 1), round(prod, 1), len(games)))

    rows.sort(key=lambda r: r.value, reverse=True)
    min_games = 15
    reliable = [r for r in rows if r.games >= min_games]
    # Watch-outs: highly valued but on a small sample (the model's known weak spot).
    watchouts = [r for r in rows[:25] if r.games < min_games]
    return Validation(
        num_players=len(rows),
        corr_value_production=_pearson(values, prods),
        corr_value_minutes=_pearson(values, mins),
        min_games=min_games,
        top=reliable[:10],
        watchouts=watchouts[:5],
    )
