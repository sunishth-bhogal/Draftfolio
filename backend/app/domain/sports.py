"""Multi-sport production models.

Each sport maps a per-game box score to a single ``production`` number; value is
then ``production × scale``, adjusted for form and shrunk toward a prior (see
player_value). Because production is linear in the stats, a season's value equals
the mean of per-game productions — so the same pipeline serves every sport, and
adding soccer/baseball later is just another entry here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SportModel:
    code: str
    scale: float
    # per-stat weights and the display label for each (used by the breakdown)
    weights: dict[str, float]
    labels: dict[str, str]


# NBA weights live in player_value (kept there for back-compat); mirror them here
# so the breakdown can be sport-generic.
NBA = SportModel(
    code="NBA",
    scale=12.0,
    weights={"points": 1.0, "rebounds": 1.2, "assists": 1.5, "steals": 3.0, "blocks": 3.0, "turnovers": -1.0},
    labels={"points": "Points", "rebounds": "Rebounds", "assists": "Assists", "steals": "Steals", "blocks": "Blocks", "turnovers": "Turnovers"},
)

# NHL skaters. Goals and assists dominate; shots/plus-minus/PIM are secondary.
# Scale calibrated so elite scorers land in the same range as NBA stars.
NHL = SportModel(
    code="NHL",
    scale=110.0,
    weights={"goals": 3.0, "assists": 2.0, "shots": 0.5, "plus_minus": 0.3, "pim": 0.05},
    labels={"goals": "Goals", "assists": "Assists", "shots": "Shots", "plus_minus": "+/-", "pim": "PIM"},
)

SPORTS: dict[str, SportModel] = {NBA.code: NBA, NHL.code: NHL}


def production_from_stats(sport: str, stats: dict[str, float]) -> float:
    """Weighted per-game production for a sport, floored at 0."""
    model = SPORTS[sport]
    return max(0.0, sum(model.weights.get(k, 0.0) * float(stats.get(k, 0.0)) for k in model.weights))


def value_components(sport: str, stats: dict[str, float]) -> dict[str, float]:
    """Per-stat dollar contribution (weight × stat × scale), for the breakdown."""
    model = SPORTS[sport]
    return {k: round(model.weights[k] * float(stats.get(k, 0.0)) * model.scale, 2) for k in model.weights}
