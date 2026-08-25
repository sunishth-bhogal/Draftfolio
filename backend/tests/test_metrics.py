"""Unit tests for the pure metrics — deterministic, known-answer checks."""

from __future__ import annotations

import math

from app.domain import metrics


def approx(a, b, tol=1e-9):
    return abs(a - b) < tol


def test_cumulative_return():
    # (1 + 0.1)(1 - 0.1) - 1 = 1.1 * 0.9 - 1 = -0.01
    assert approx(metrics.cumulative_return([0.1, -0.1]), 1.1 * 0.9 - 1)
    assert approx(metrics.cumulative_return([0.0, 0.0]), 0.0)


def test_volatility_and_sharpe_signs():
    up = [0.01, 0.02, 0.015, 0.005]
    vol = metrics.annualized_volatility(up)
    assert vol is not None and vol > 0
    sharpe = metrics.sharpe_ratio(up)
    assert sharpe is not None and sharpe > 0  # all-positive returns => positive sharpe


def test_zero_volatility_returns_none():
    flat = [0.01, 0.01, 0.01]
    assert metrics.annualized_volatility(flat) == 0.0
    assert metrics.sharpe_ratio(flat) is None  # divide-by-zero guarded


def test_max_drawdown():
    # 100 -> 120 -> 90 -> 110 : worst peak(120)->trough(90) = -25%
    curve = [100, 120, 90, 110]
    assert approx(metrics.max_drawdown(curve), 0.25)
    assert metrics.max_drawdown([100]) is None


def test_beta_of_identical_series_is_one():
    r = [0.01, -0.02, 0.03, 0.00, 0.015]
    assert approx(metrics.beta(r, r), 1.0, tol=1e-9)
    assert approx(metrics.alpha(r, r), 0.0, tol=1e-9)  # no excess over itself
    assert approx(metrics.tracking_error(r, r), 0.0, tol=1e-9)


def test_beta_scales_with_amplitude():
    b = [0.01, -0.02, 0.03, 0.00, 0.015]
    r = [2 * x for x in b]  # portfolio is 2x the benchmark
    assert approx(metrics.beta(r, b), 2.0, tol=1e-9)


def test_diversification():
    # five equal weights => HHI 0.2, effective holdings 5
    w = [0.2, 0.2, 0.2, 0.2, 0.2]
    assert approx(metrics.herfindahl(w), 0.2)
    assert approx(metrics.effective_holdings(w), 5.0)
    # one dominant name => effective holdings near 1
    w2 = [0.96, 0.01, 0.01, 0.01, 0.01]
    assert metrics.effective_holdings(w2) < 1.1


def test_insufficient_data_returns_none():
    assert metrics.annualized_volatility([0.01]) is None
    assert metrics.sharpe_ratio([]) is None
    assert metrics.beta([0.01], [0.01]) is None
