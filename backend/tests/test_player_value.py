"""Unit tests for the player valuation model."""

from __future__ import annotations

from app.domain.player_value import (
    FLOOR,
    PlayerStats,
    form_multiplier,
    production_score,
    value_index,
)


def _star() -> PlayerStats:
    return PlayerStats(games=70, minutes=36, points=30, rebounds=8, assists=8,
                       steals=1.5, blocks=1.0, turnovers=3.0)


def _role() -> PlayerStats:
    return PlayerStats(games=60, minutes=20, points=7, rebounds=3, assists=1.5,
                       steals=0.5, blocks=0.3, turnovers=1.0)


def test_star_worth_more_than_role_player():
    assert value_index(_star()) > value_index(_role())


def test_no_games_falls_to_floor():
    dnp = PlayerStats(games=0, minutes=0, points=0, rebounds=0, assists=0,
                      steals=0, blocks=0, turnovers=0)
    assert value_index(dnp) == FLOOR


def test_injury_haircut_lowers_value():
    s = _star()
    assert value_index(s, available=False) < value_index(s, available=True)


def test_hot_form_raises_value():
    s = _star()
    assert value_index(s, form_multiplier=1.25) > value_index(s, form_multiplier=1.0)


def test_form_multiplier_clamped():
    assert form_multiplier(100, 10) == 1.25  # capped up
    assert form_multiplier(1, 10) == 0.8  # capped down
    assert form_multiplier(10, 0) == 1.0  # no baseline -> neutral


def test_turnovers_reduce_production():
    base = PlayerStats(70, 36, 30, 8, 8, 1.5, 1.0, 0.0)
    turnover_heavy = PlayerStats(70, 36, 30, 8, 8, 1.5, 1.0, 6.0)
    assert production_score(turnover_heavy) < production_score(base)


def test_reliability_and_shrinkage_math():
    from app.domain.player_value import reliability, shrink

    # Matches the spec example: 1-game $670 obs, $180 prior, K=12 -> ~$218.
    assert round(reliability(1, 12), 3) == round(1 / 13, 3)
    assert abs(shrink(670, 180, 1, 12) - 217.69) < 0.5

    # Full season -> mostly observed; returning star (thin sample, high prior)
    # is pulled toward the prior, NOT toward zero.
    assert shrink(670, 180, 60, 12) > 550
    assert shrink(200, 400, 2, 12) > 350  # not worthless


def test_shrink_with_equal_prior_is_identity():
    from app.domain.player_value import shrink

    assert shrink(300, 300, 5, 12) == 300.0
