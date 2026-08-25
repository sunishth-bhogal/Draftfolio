"""Leaderboard endpoint — scores all portfolios as one implicit league."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.scoring import MODE_WEIGHTS, ScoreMode
from app.services import scoring as scoring_service

router = APIRouter()


class LeaderboardRowOut(BaseModel):
    portfolio_id: uuid.UUID
    name: str
    rank: int
    score: float
    percentiles: dict[str, float]
    cumulative_return: float | None
    benchmark_return: float | None
    max_drawdown: float | None
    effective_holdings: float | None
    notes: list[str]


class LeaderboardOut(BaseModel):
    mode: str
    weights: dict[str, float]
    benchmark: str | None
    rows: list[LeaderboardRowOut]


@router.get("/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(
    mode: ScoreMode = ScoreMode.BALANCED,
    benchmark: str | None = None,
    rf: float = 0.0,
    db: Session = Depends(get_db),
) -> LeaderboardOut:
    ids = scoring_service.all_portfolio_ids(db)
    rows = scoring_service.score_league(db, ids, mode=mode, benchmark=benchmark, rf=rf)
    return LeaderboardOut(
        mode=mode.value,
        weights=MODE_WEIGHTS[mode],  # surfaced so the UI can explain the score
        benchmark=benchmark,
        rows=[LeaderboardRowOut(**row.__dict__) for row in rows],
    )
