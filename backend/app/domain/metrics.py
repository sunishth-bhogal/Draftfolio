"""Risk and performance metrics — pure functions over return/weight series.

Deliberately float, not Decimal: unlike the ledger (where a rounded cent is
money created or destroyed), these are statistical *estimates* — a Sharpe ratio
is already an approximation of an unknowable population quantity, so exact
decimal arithmetic would be false precision. Money stays Decimal; risk stats are
float. Keeping this module free of DB/framework imports means every formula
below is unit-tested directly.

Conventions:
* ``returns`` are per-period simple returns (e.g. daily).
* ``periods_per_year`` annualizes; default 252 trading days. It is an explicit
  assumption, not a fact — short seasons should say so in the UI.
* Functions return ``None`` when there isn't enough data to compute a value,
  rather than raising, so callers can render "n/a".
"""

from __future__ import annotations

import math
import statistics
from typing import Sequence

TRADING_DAYS = 252


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def cumulative_return(returns: Sequence[float]) -> float:
    """Total compounded return over the series."""
    product = 1.0
    for r in returns:
        product *= 1.0 + r
    return product - 1.0


def annualized_return(returns: Sequence[float], periods_per_year: int = TRADING_DAYS) -> float | None:
    if not returns:
        return None
    total = cumulative_return(returns)
    years = len(returns) / periods_per_year
    if years <= 0:
        return None
    return (1.0 + total) ** (1.0 / years) - 1.0


def annualized_volatility(
    returns: Sequence[float], periods_per_year: int = TRADING_DAYS
) -> float | None:
    if len(returns) < 2:
        return None
    return statistics.stdev(returns) * math.sqrt(periods_per_year)  # sample stdev (ddof=1)


def sharpe_ratio(
    returns: Sequence[float], rf_annual: float = 0.0, periods_per_year: int = TRADING_DAYS
) -> float | None:
    """Annualized excess return per unit of total volatility."""
    if len(returns) < 2:
        return None
    rf_period = rf_annual / periods_per_year
    excess = [r - rf_period for r in returns]
    sd = statistics.stdev(returns)
    if sd == 0:
        return None
    return (_mean(excess) / sd) * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: Sequence[float], rf_annual: float = 0.0, periods_per_year: int = TRADING_DAYS
) -> float | None:
    """Like Sharpe, but penalizes only downside deviation."""
    if len(returns) < 2:
        return None
    rf_period = rf_annual / periods_per_year
    excess = [r - rf_period for r in returns]
    downside = [min(0.0, e) for e in excess]
    downside_dev = math.sqrt(sum(d * d for d in downside) / len(downside))
    if downside_dev == 0:
        return None
    return (_mean(excess) / downside_dev) * math.sqrt(periods_per_year)


def max_drawdown(equity_curve: Sequence[float]) -> float | None:
    """Largest peak-to-trough decline, as a positive fraction (0.15 = -15%)."""
    if len(equity_curve) < 2:
        return None
    peak = equity_curve[0]
    worst = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak
            worst = min(worst, dd)
    return -worst


def beta(returns: Sequence[float], benchmark: Sequence[float]) -> float | None:
    """Sensitivity of portfolio returns to the benchmark: cov / var."""
    n = len(returns)
    if n < 2 or n != len(benchmark):
        return None
    mr, mb = _mean(returns), _mean(benchmark)
    cov = sum((returns[i] - mr) * (benchmark[i] - mb) for i in range(n)) / (n - 1)
    var = sum((b - mb) ** 2 for b in benchmark) / (n - 1)
    if var == 0:
        return None
    return cov / var


def alpha(
    returns: Sequence[float],
    benchmark: Sequence[float],
    rf_annual: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float | None:
    """Annualized CAPM alpha: return not explained by benchmark exposure."""
    b = beta(returns, benchmark)
    if b is None:
        return None
    rf_period = rf_annual / periods_per_year
    excess_r = _mean(returns) - rf_period
    excess_b = _mean(benchmark) - rf_period
    return (excess_r - b * excess_b) * periods_per_year


def tracking_error(
    returns: Sequence[float], benchmark: Sequence[float], periods_per_year: int = TRADING_DAYS
) -> float | None:
    """Annualized stdev of the return difference vs the benchmark."""
    n = len(returns)
    if n < 2 or n != len(benchmark):
        return None
    diff = [returns[i] - benchmark[i] for i in range(n)]
    return statistics.stdev(diff) * math.sqrt(periods_per_year)


def herfindahl(weights: Sequence[float]) -> float:
    """Concentration index: sum of squared weights (1.0 = everything in one name)."""
    return sum(w * w for w in weights)


def effective_holdings(weights: Sequence[float]) -> float | None:
    """Effective number of independent-ish positions = 1 / HHI.

    Five equal holdings -> 5.0; a book dominated by one name -> close to 1.0.
    """
    h = herfindahl(weights)
    return (1.0 / h) if h > 0 else None
