"""Player pack — cooldown status + open."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import auth as auth_svc
from app.services import daily as pack

router = APIRouter()


class StatusOut(BaseModel):
    can_claim: bool
    seconds_remaining: int
    streak: int
    cooldown_hours: int


class PackOut(BaseModel):
    instrument_id: str
    player: str
    sport: str | None
    headshot_url: str | None
    tier: str
    shares: int
    value: float
    xp_awarded: int
    streak: int


@router.get("/pack/status", response_model=StatusOut)
def pack_status(user: User = Depends(auth_svc.current_user), db: Session = Depends(get_db)) -> StatusOut:
    return StatusOut(**pack.status(db, user).__dict__)


@router.post("/pack/open", response_model=PackOut)
def pack_open(user: User = Depends(auth_svc.current_user), db: Session = Depends(get_db)) -> PackOut:
    try:
        res = pack.claim(db, user)
    except pack.OnCooldown as e:
        raise HTTPException(status_code=409, detail=f"on cooldown ({e.seconds}s)")
    return PackOut(**res.__dict__)
