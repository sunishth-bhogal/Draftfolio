"""Scoring — pure functions that turn per-portfolio components into a ranked score.

The product's core idea is competing on *risk-adjusted* investing, not raw
return. Two design choices enforce that:

* **Percentile ranks, not raw values.** Each component is converted to its rank
  within the cohort before weighting, so one extreme portfolio can't dominate a
  league by taking wild risk — it can only ever reach the top *percentile*, and
  the risk components pull the other way.
* **Transparent, reweightable modes.** The same four components (Return,
  Benchmark-relative, Drawdown-control, Diversification) are combined with mode
  weights the UI can show in plain language.

All components are "higher is better" *before* ranking (drawdown is passed in as
its negative, so less drawdown ranks higher).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class ScoreMode(str, Enum):
    SPRINT = "SPRINT"  # mostly total return
    BALANCED = "BALANCED"  # return plus risk control
    INVESTOR = "INVESTOR"  # risk-adjusted return and diversification


# Weights over components R, B, D, C. Each row sums to 1.0.
MODE_WEIGHTS: dict[ScoreMode, dict[str, float]] = {
    ScoreMode.SPRINT: {"R": 0.85, "B": 0.10, "D": 0.05, "C": 0.00},
    ScoreMode.BALANCED: {"R": 0.50, "B": 0.20, "D": 0.15, "C": 0.15},
    ScoreMode.INVESTOR: {"R": 0.30, "B": 0.20, "D": 0.25, "C": 0.25},
}


@dataclass
class Components:
    """Raw, higher-is-better component values for one portfolio."""

    R: float  # return
    B: float  # benchmark-relative return
    D: float  # drawdown control (= -max_drawdown)
    C: float  # diversification (effective holdings)


@dataclass
class ScoredPortfolio:
    index: int  # position in the input cohort
    components: Components
    percentiles: dict[str, float]  # per-component percentile in [0,1]
    score: float  # composite in [0, 100]


def percentile_ranks(values: Sequence[float]) -> list[float]:
    """Percentile rank of each value within the list, in [0, 1].

    Uses the mean-rank convention ``(below + 0.5*equal) / n`` so ties share a
    rank and a lone portfolio scores a neutral 0.5.
    """
    n = len(values)
    if n == 0:
        return []
    ranks: list[float] = []
    for v in values:
        below = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v)
        ranks.append((below + 0.5 * equal) / n)
    return ranks


def score_cohort(cohort: Sequence[Components], mode: ScoreMode) -> list[ScoredPortfolio]:
    """Rank each component across the cohort, weight by mode, scale to 0-100."""
    weights = MODE_WEIGHTS[mode]
    pr = {
        "R": percentile_ranks([c.R for c in cohort]),
        "B": percentile_ranks([c.B for c in cohort]),
        "D": percentile_ranks([c.D for c in cohort]),
        "C": percentile_ranks([c.C for c in cohort]),
    }

    scored: list[ScoredPortfolio] = []
    for i, comp in enumerate(cohort):
        percentiles = {k: pr[k][i] for k in ("R", "B", "D", "C")}
        composite = sum(weights[k] * percentiles[k] for k in ("R", "B", "D", "C"))
        scored.append(
            ScoredPortfolio(
                index=i,
                components=comp,
                percentiles=percentiles,
                score=round(composite * 100.0, 2),
            )
        )
    return scored
