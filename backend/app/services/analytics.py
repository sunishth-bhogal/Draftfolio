"""Analytics service — turns stored snapshots/prices into risk metrics.

Pulls the portfolio's snapshot equity curve (and its per-interval returns), an
optional benchmark's returns aligned over the *same* intervals, and current
holding weights, then delegates every number to the pure ``domain.metrics``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import metrics
from app.models import Instrument, PortfolioSnapshot, PriceBar
from app.services.valuation import return_series, value_portfolio


@dataclass
class Analytics:
    periods: int  # number of return observations
    cumulative_return: float | None = None
    annualized_return: float | None = None
    annualized_volatility: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None
    # benchmark-relative (None if no/insufficient benchmark data)
    benchmark: str | None = None
    beta: float | None = None
    alpha: float | None = None
    tracking_error: float | None = None
    # diversification (from current weights)
    hhi: float | None = None
    effective_holdings: float | None = None
    notes: list[str] = field(default_factory=list)


def _benchmark_returns(
    db: Session, symbol: str, snapshot_dates: list[date]
) -> list[float] | None:
    """Benchmark simple returns over the same consecutive-snapshot intervals."""
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if inst is None:
        return None
    closes: list[float] = []
    for d in snapshot_dates:
        bar = db.scalar(
            select(PriceBar)
            .where(PriceBar.instrument_id == inst.id, PriceBar.bar_date == d)
            .order_by(PriceBar.as_of.desc())
            .limit(1)
        )
        if bar is None:
            return None  # can't align — missing a mark on a snapshot date
        closes.append(float(bar.close))
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def portfolio_analytics(
    db: Session,
    portfolio_id: uuid.UUID,
    base_currency: str,
    *,
    benchmark: str | None = None,
    rf_annual: float = 0.0,
    periods_per_year: int = metrics.TRADING_DAYS,
) -> Analytics:
    series = return_series(db, portfolio_id)
    returns = [float(p.daily_return) for p in series if p.daily_return is not None]
    equity_curve = [float(p.equity) for p in series]
    snapshot_dates = [p.snapshot_date for p in series]

    result = Analytics(periods=len(returns))
    if len(returns) < 2:
        result.notes.append("need >= 2 daily snapshots for risk metrics")
    else:
        result.cumulative_return = metrics.cumulative_return(returns)
        result.annualized_return = metrics.annualized_return(returns, periods_per_year)
        result.annualized_volatility = metrics.annualized_volatility(returns, periods_per_year)
        result.sharpe = metrics.sharpe_ratio(returns, rf_annual, periods_per_year)
        result.sortino = metrics.sortino_ratio(returns, rf_annual, periods_per_year)
        result.max_drawdown = metrics.max_drawdown(equity_curve)

    # benchmark-relative
    if benchmark and len(returns) >= 2:
        bench = _benchmark_returns(db, benchmark, snapshot_dates)
        if bench is None or len(bench) != len(returns):
            result.notes.append(f"insufficient benchmark data for {benchmark}")
        else:
            result.benchmark = benchmark
            result.beta = metrics.beta(returns, bench)
            result.alpha = metrics.alpha(returns, bench, rf_annual, periods_per_year)
            result.tracking_error = metrics.tracking_error(returns, bench, periods_per_year)

    # diversification from current holdings
    val = value_portfolio(db, portfolio_id, base_currency)
    if val.market_value and val.holdings:
        weights = [float(h.market_value) / float(val.market_value) for h in val.holdings]
        result.hhi = metrics.herfindahl(weights)
        result.effective_holdings = metrics.effective_holdings(weights)
    else:
        result.notes.append("no priced holdings for diversification")

    return result
