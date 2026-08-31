"""NBA backfill — thin adapter over the sport-agnostic pipeline.

Kept as a stable entry point (used by scripts/tests). Converts typed NBA
``GameObs`` into the generic form and delegates to ``player_backfill``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Instrument
from app.services.nba_espn import GameObs
from app.services.player_backfill import GenericGame, backfill_player_generic


def backfill_player(db: Session, instrument: Instrument, games: list[GameObs]) -> int:
    generic = [
        GenericGame(
            espn_event_id=g.espn_event_id,
            game_date=g.game_date,
            opponent=g.opponent,
            home=g.home,
            minutes=g.minutes,
            stats={
                "points": g.points,
                "rebounds": g.rebounds,
                "assists": g.assists,
                "steals": g.steals,
                "blocks": g.blocks,
                "turnovers": g.turnovers,
            },
        )
        for g in games
    ]
    return backfill_player_generic(db, instrument, generic, sport="NBA")
