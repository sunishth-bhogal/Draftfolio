"""Scoring service — builds a leaderboard by scoring a cohort of portfolios.

Gathers each portfolio's analytics, maps them to the four higher-is-better
components, and delegates ranking/weighting to the pure domain. With no leagues
yet, the endpoint scores *all* portfolios as one implicit league; the service
itself takes an explicit id list so real leagues drop in unchanged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import scoring
from app.domain.scoring import Components, ScoreMode
from app.models import Portfolio
from app.services.analytics import portfolio_analytics


@dataclass
class LeaderboardRow:
    portfolio_id: uuid.UUID
    name: str
    rank: int
    score: float
    percentiles: dict[str, float]
    cumulative_return: float | None
    benchmark_return: float | None
    max_drawdown: float | None
    effective_holdings: float | None
    notes: list[str] = field(default_factory=list)


def _components_for(db: Session, pf: Portfolio, benchmark: str | None, rf: float) -> tuple[Components, dict]:
    a = portfolio_analytics(db, pf.id, pf.base_currency, benchmark=benchmark, rf_annual=rf)
    R = a.cumulative_return or 0.0
    B = (
        (a.cumulative_return - a.benchmark_return)
        if (a.cumulative_return is not None and a.benchmark_return is not None)
        else 0.0
    )
    # Drawdown control: less drawdown is better, so negate. None (insufficient) => 0.
    D = -(a.max_drawdown) if a.max_drawdown is not None else 0.0
    C = a.effective_holdings or 0.0
    meta = {
        "cumulative_return": a.cumulative_return,
        "benchmark_return": a.benchmark_return,
        "max_drawdown": a.max_drawdown,
        "effective_holdings": a.effective_holdings,
        "notes": a.notes,
    }
    return Components(R=R, B=B, D=D, C=C), meta


def score_league(
    db: Session,
    portfolio_ids: list[uuid.UUID],
    *,
    mode: ScoreMode = ScoreMode.BALANCED,
    benchmark: str | None = None,
    rf: float = 0.0,
) -> list[LeaderboardRow]:
    portfolios = [db.get(Portfolio, pid) for pid in portfolio_ids]
    portfolios = [p for p in portfolios if p is not None]

    cohort: list[Components] = []
    metas: list[dict] = []
    for pf in portfolios:
        comp, meta = _components_for(db, pf, benchmark, rf)
        cohort.append(comp)
        metas.append(meta)

    scored = scoring.score_cohort(cohort, mode)
    # Rank by composite score, highest first.
    order = sorted(range(len(scored)), key=lambda i: scored[i].score, reverse=True)

    rows: list[LeaderboardRow] = []
    for rank, i in enumerate(order, start=1):
        pf = portfolios[i]
        s = scored[i]
        m = metas[i]
        rows.append(
            LeaderboardRow(
                portfolio_id=pf.id,
                name=pf.name,
                rank=rank,
                score=s.score,
                percentiles={k: round(v, 4) for k, v in s.percentiles.items()},
                cumulative_return=m["cumulative_return"],
                benchmark_return=m["benchmark_return"],
                max_drawdown=m["max_drawdown"],
                effective_holdings=m["effective_holdings"],
                notes=m["notes"],
            )
        )
    return rows


def all_portfolio_ids(db: Session) -> list[uuid.UUID]:
    return list(db.scalars(select(Portfolio.id)))
