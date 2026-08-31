"""Tests for the sport-generic pipeline via NHL (hockey)."""

from __future__ import annotations

from datetime import date, timedelta

from app.domain.player_value import value_from_production
from app.domain.sports import NHL, production_from_stats, value_components
from app.models import Instrument, PriceBar
from app.services.catalysts import player_catalysts
from app.services.player_analysis import value_breakdown_for
from app.services.player_backfill import GenericGame, backfill_player_generic


def test_nhl_production_weights_goals_over_shots():
    scorer = {"goals": 1.0, "assists": 1.0, "shots": 3.0, "plus_minus": 1.0, "pim": 0.0}
    shooter = {"goals": 0.0, "assists": 0.0, "shots": 6.0, "plus_minus": 0.0, "pim": 0.0}
    assert production_from_stats("NHL", scorer) > production_from_stats("NHL", shooter)


def _nhl_player(db) -> Instrument:
    inst = Instrument(
        symbol="NHL:1", name="Test Skater", currency="CAD", asset_class="PLAYER",
        sport="NHL", position="C", prior_value=200.0, prior_basis="24-25",
    )
    db.add(inst)
    db.commit()
    return inst


def _games(n, goals):
    out = []
    for i in range(n):
        out.append(
            GenericGame(
                espn_event_id=f"e{i}", game_date=date(2026, 1, 1) + timedelta(days=i * 2),
                opponent="TOR", home=True, minutes=19.5,
                stats={"goals": goals, "assists": 1.0, "shots": 4.0, "plus_minus": 1.0, "pim": 0.0},
            )
        )
    return out


def test_nhl_backfill_and_breakdown(db_session):
    inst = _nhl_player(db_session)
    bars = backfill_player_generic(db_session, inst, _games(20, goals=0.6), sport="NHL")
    assert bars == 20

    b = value_breakdown_for(db_session, inst.id)
    assert b.available and b.games == 20
    # Hockey components, not basketball.
    assert set(b.components) == set(NHL.weights)
    assert "goals" in b.components and "points" not in b.components
    # Value reconciles to production × scale (pre-shrink), within rounding.
    expected = value_from_production(
        production_from_stats("NHL", {"goals": 0.6, "assists": 1.0, "shots": 4.0, "plus_minus": 1.0, "pim": 0.0}),
        NHL.scale,
    )
    assert abs(b.observed_value - expected) < 1.0
    # Components sum to base value.
    assert abs(sum(b.components.values()) - b.base_value) < 1.0


def test_nhl_catalyst_uses_hockey_box_line(db_session):
    inst = _nhl_player(db_session)
    games = _games(9, goals=0.0)
    # A hat trick in the latest game.
    games.append(
        GenericGame("hot", date(2026, 3, 1), "MTL", True, 22.0,
                    {"goals": 3.0, "assists": 1.0, "shots": 7.0, "plus_minus": 3.0, "pim": 0.0})
    )
    backfill_player_generic(db_session, inst, games, sport="NHL")
    c = player_catalysts(db_session, inst.id)
    perf = next(x for x in c.items if x.kind == "performance")
    assert "G" in perf.detail and "SOG" in perf.detail  # hockey box line
    assert perf.direction == "up"


def test_nba_components_still_basketball(db_session):
    inst = Instrument(symbol="NBA:x", name="Hooper", currency="CAD", asset_class="PLAYER",
                      sport="NBA", position="G", prior_value=300.0)
    db_session.add(inst); db_session.commit()
    games = [
        GenericGame(f"g{i}", date(2026, 1, 1) + timedelta(days=i), "LAL", True, 34.0,
                    {"points": 25, "rebounds": 5, "assists": 6, "steals": 1, "blocks": 0.5, "turnovers": 2})
        for i in range(15)
    ]
    backfill_player_generic(db_session, inst, games, sport="NBA")
    b = value_breakdown_for(db_session, inst.id)
    assert "points" in b.components and "goals" not in b.components
