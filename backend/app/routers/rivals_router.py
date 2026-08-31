"""Rivals — division standings for the logged-in user."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import auth as auth_svc
from app.services import rivals
from app.services.rivals import DIVISIONS

router = APIRouter()


class StandingOut(BaseModel):
    username: str
    display_name: str
    level: int
    xp: int
    division_points: int
    is_me: bool


class RivalsOut(BaseModel):
    division: str
    divisions: list[str]
    promote_at: int
    relegate_at: int
    standings: list[StandingOut]


@router.get("/rivals", response_model=RivalsOut)
def my_rivals(user: User = Depends(auth_svc.current_user), db: Session = Depends(get_db)) -> RivalsOut:
    rows = rivals.division_standings(db, user.division, me_id=user.id)
    return RivalsOut(
        division=user.division,
        divisions=DIVISIONS,
        promote_at=rivals.PROMOTE_AT,
        relegate_at=rivals.RELEGATE_AT,
        standings=[StandingOut(**r.__dict__) for r in rows],
    )
