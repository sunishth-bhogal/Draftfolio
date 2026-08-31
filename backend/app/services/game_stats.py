"""Read a game's stats/production in a sport-agnostic, back-compatible way.

Prefers the stored JSON stats + production; falls back to the typed NBA columns
for older/hand-built rows (and tests). One place so breakdown, catalysts, and
validation all agree.
"""

from __future__ import annotations

import json

from app.domain.sports import production_from_stats
from app.models import PlayerGame

_NBA_KEYS = ("points", "rebounds", "assists", "steals", "blocks", "turnovers")


def game_stats(g: PlayerGame) -> dict[str, float]:
    if g.stats_json:
        return {k: float(v) for k, v in json.loads(g.stats_json).items()}
    return {k: float(getattr(g, k) or 0.0) for k in _NBA_KEYS}


def game_production(g: PlayerGame, sport: str) -> float:
    if g.production is not None:
        return g.production
    return production_from_stats(sport, game_stats(g))
