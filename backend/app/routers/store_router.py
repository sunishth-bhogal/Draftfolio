"""Pack store — list tiers + open a paid pack."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Portfolio, User
from app.services import auth as auth_svc
from app.services import store as store_svc

router = APIRouter()


class TierOut(BaseModel):
    key: str
    name: str
    cost: int
    cards: int
    weights: dict[str, int]
    guarantee: str | None
    blurb: str


class StoreOut(BaseModel):
    cash: float
    tiers: list[TierOut]


class CardOut(BaseModel):
    instrument_id: str
    player: str
    sport: str | None
    headshot_url: str | None
    tier: str
    value: float


class OpenOut(BaseModel):
    tier: str
    cost: int
    cards: list[CardOut]
    total_value: float
    cash: float


class OpenRequest(BaseModel):
    tier: str


@router.get("/store", response_model=StoreOut)
def store(user: User = Depends(auth_svc.current_user), db: Session = Depends(get_db)) -> StoreOut:
    pf = db.scalar(select(Portfolio).where(Portfolio.user_id == user.id).limit(1))
    cash = store_svc.cash_of(db, pf) if pf else 0.0
    return StoreOut(
        cash=cash,
        tiers=[TierOut(**t.__dict__) for t in store_svc.TIERS],
    )


@router.post("/store/open", response_model=OpenOut)
def store_open(body: OpenRequest, user: User = Depends(auth_svc.current_user), db: Session = Depends(get_db)) -> OpenOut:
    if body.tier not in store_svc.TIER_BY_KEY:
        raise HTTPException(status_code=404, detail="unknown pack")
    try:
        res = store_svc.open_pack(db, user, body.tier)
    except store_svc.NotEnoughCash as e:
        raise HTTPException(status_code=422, detail=str(e))
    return OpenOut(
        tier=res.tier, cost=res.cost, total_value=res.total_value, cash=res.cash,
        cards=[CardOut(**c.__dict__) for c in res.cards],
    )
