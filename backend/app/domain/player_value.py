"""Player valuation model — turns box-score stats into a tradeable value index.

This is the "model that predicts a player's value." It is deliberately
transparent (like the risk metrics): a weighted production score scaled to a
dollar value, adjusted for recent form and availability. That way a value move
is always explainable — "up because points-per-game rose", not a black box.

Value behaves like a price: it drifts with production and jumps on news
(injuries cut availability; a hot streak lifts the form multiplier). The nightly
job recomputes it from fresh stats.

Units are dimensionless "dollars" — a share of a player. Superstars land in the
few-hundreds, rotation players in the tens, so a virtual salary cap forces real
roster choices.
"""

from __future__ import annotations

from dataclasses import dataclass

# Per-game production weights (a value-over-replacement style box score).
W_PTS = 1.0
W_REB = 1.2
W_AST = 1.5
W_STL = 3.0
W_BLK = 3.0
W_TOV = -1.0

VALUE_SCALE = 12.0  # dollars per production point
FLOOR = 5.0  # a rostered player is never worth nothing


@dataclass(frozen=True)
class PlayerStats:
    games: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float


def production_score(s: PlayerStats) -> float:
    """Per-game weighted contribution. Higher = more valuable on the court."""
    return max(
        0.0,
        W_PTS * s.points
        + W_REB * s.rebounds
        + W_AST * s.assists
        + W_STL * s.steals
        + W_BLK * s.blocks
        + W_TOV * s.turnovers,
    )


def value_index(
    stats: PlayerStats,
    *,
    form_multiplier: float = 1.0,
    available: bool = True,
) -> float:
    """Dollar value of one share of a player.

    ``form_multiplier`` (recent games vs season, ~0.8–1.25) tilts the price for
    hot/cold streaks. ``available`` applies an injury/out haircut. Players with
    no games played fall back to the floor until they log minutes.
    """
    if stats.games <= 0:
        return FLOOR
    base = production_score(stats) * VALUE_SCALE
    value = base * form_multiplier
    if not available:
        value *= 0.6  # sidelined players are worth less to a fantasy owner
    return round(max(FLOOR, value), 2)


def form_multiplier(recent_score: float, season_score: float) -> float:
    """Recent form vs season baseline, clamped to a sane band."""
    if season_score <= 0:
        return 1.0
    ratio = recent_score / season_score
    return max(0.8, min(1.25, ratio))
