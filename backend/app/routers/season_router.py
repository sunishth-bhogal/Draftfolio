"""Season info + (admin) end-of-season finalize."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import auth as auth_svc
from app.services import season as season_svc

router = APIRouter()


class SeasonOut(BaseModel):
    name: str
    start_date: date
    end_date: date
    total_gameweeks: int
    current_gameweek: int
    status: str
    your_division: str | None = None
    your_points: int | None = None
    your_rank: int | None = None


@router.get("/season", response_model=SeasonOut)
def current_season(
    user: User | None = Depends(auth_svc.optional_user), db: Session = Depends(get_db)
) -> SeasonOut:
    return SeasonOut(**season_svc.season_state(db, user).__dict__)
