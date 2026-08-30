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
    reliability,
    shrink,
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
    as_of: object | None = None
    averages: dict[str, float] = field(default_factory=dict)
    components: dict[str, float] = field(default_factory=dict)  # per-stat $ contribution
    base_value: float = 0.0
    form_multiplier: float = 1.0
    form_adjustment: float = 0.0
    observed_value: float = 0.0  # this season's production value (pre-shrinkage)
    prior_value: float = 0.0  # player-quality prior
    prior_basis: str | None = None
    reliability: float = 0.0  # current-season confidence, G/(G+K)
    final_value: float = 0.0  # shrunk value actually shown/traded


def value_breakdown_for(db: Session, instrument_id: uuid.UUID) -> Breakdown:
    inst = db.get(Instrument, instrument_id)
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
    games = len(rows)

    base = round(max(FLOOR, production_score(season) * 12.0), 2)  # VALUE_SCALE
    observed = value_index(season, form_multiplier=form)  # pre-shrinkage
    prior = float(inst.prior_value) if inst and inst.prior_value is not None else observed
    rel = reliability(games)
    adjusted = shrink(observed, prior, games)

    return Breakdown(
        available=True,
        games=games,
        as_of=rows[-1].game_date,
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
        observed_value=observed,
        prior_value=round(prior, 2),
        prior_basis=inst.prior_basis if inst else None,
        reliability=round(rel, 4),
        final_value=adjusted,
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


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


@dataclass
class ValidationRow:
    name: str
    value: float
    ppg: float
    production: float
    games: int


@dataclass
class PositionRow:
    position: str
    n: int
    avg_value: float
    avg_production: float


@dataclass
class Validation:
    num_players: int
    min_games: int
    # sanity vs face-validity correlations (Pearson + Spearman)
    pearson_value_production: float | None
    spearman_value_production: float | None
    pearson_value_minutes: float | None
    spearman_value_minutes: float | None
    # walk-forward predictive test (no leakage): past value -> future production
    predictive_n: int
    predictive_pearson: float | None
    predictive_spearman: float | None
    top: list[ValidationRow] = field(default_factory=list)
    watchouts: list[ValidationRow] = field(default_factory=list)
    by_position: list[PositionRow] = field(default_factory=list)


def _future_split_value(games: list[PlayerGame]) -> tuple[float, float] | None:
    """Value from the first half of games; mean production over the second half.

    Chronological split so the value never sees the games it's judged against.
    """
    if len(games) < 10:
        return None
    games = sorted(games, key=lambda g: g.game_date)
    h = len(games) // 2
    train, test = games[:h], games[h:]
    if not test:
        return None
    tstats = _mean_stats(train)
    recent = _mean_stats(train[-FORM_WINDOW:])
    form = form_multiplier(production_score(recent), production_score(tstats))
    value = value_index(tstats, form_multiplier=form)
    future = sum(production_score(_mean_stats([g])) for g in test) / len(test)
    return value, future


def league_validation(db: Session) -> Validation:
    players = db.scalars(
        select(Instrument).where(Instrument.asset_class == "PLAYER")
    ).all()

    values: list[float] = []
    prods: list[float] = []
    mins: list[float] = []
    rows: list[ValidationRow] = []
    pos_values: dict[str, list[float]] = {}
    pos_prods: dict[str, list[float]] = {}
    train_vals: list[float] = []
    future_prods: list[float] = []

    for p in players:
        games = list(db.scalars(select(PlayerGame).where(PlayerGame.instrument_id == p.id)))
        if not games:
            continue
        s = _mean_stats(games)
        prod = production_score(s)
        val = value_index(s)
        values.append(val)
        prods.append(prod)
        mins.append(s.minutes)
        rows.append(ValidationRow(p.name, val, round(s.points, 1), round(prod, 1), len(games)))
        pos = p.position or "?"
        pos_values.setdefault(pos, []).append(val)
        pos_prods.setdefault(pos, []).append(prod)

        split = _future_split_value(games)
        if split is not None:
            train_vals.append(split[0])
            future_prods.append(split[1])

    rows.sort(key=lambda r: r.value, reverse=True)
    min_games = 15
    reliable = [r for r in rows if r.games >= min_games]
    watchouts = [r for r in rows[:25] if r.games < min_games]

    by_position = sorted(
        (
            PositionRow(
                position=pos,
                n=len(vals),
                avg_value=round(sum(vals) / len(vals), 1),
                avg_production=round(sum(pos_prods[pos]) / len(pos_prods[pos]), 1),
            )
            for pos, vals in pos_values.items()
        ),
        key=lambda r: r.avg_value,
        reverse=True,
    )

    return Validation(
        num_players=len(rows),
        min_games=min_games,
        pearson_value_production=_pearson(values, prods),
        spearman_value_production=_spearman(values, prods),
        pearson_value_minutes=_pearson(values, mins),
        spearman_value_minutes=_spearman(values, mins),
        predictive_n=len(train_vals),
        predictive_pearson=_pearson(train_vals, future_prods),
        predictive_spearman=_spearman(train_vals, future_prods),
        top=reliable[:10],
        watchouts=watchouts[:5],
        by_position=by_position,
    )
