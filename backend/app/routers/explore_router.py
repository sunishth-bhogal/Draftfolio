"""Explore / discovery endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import explore as explore_svc

router = APIRouter()


class MoverOut(BaseModel):
    instrument_id: str
    name: str
    sport: str | None
    team: str | None
    position: str | None
    headshot_url: str | None
    price: float
    change: float


class PopularOut(BaseModel):
    instrument_id: str
    name: str
    sport: str | None
    headshot_url: str | None
    price: float
    holders: int


class IpoOut(BaseModel):
    name: str
    sport: str
    position: str
    note: str
    list_date: str
    ipo_price: int
    status: str
    instrument_id: str | None


class ExploreOut(BaseModel):
    trending: list[MoverOut]
    popular: list[PopularOut]
    ipos: list[IpoOut]


@router.get("/explore", response_model=ExploreOut)
def explore(db: Session = Depends(get_db)) -> ExploreOut:
    e = explore_svc.explore(db)
    return ExploreOut(
        trending=[MoverOut(**m.__dict__) for m in e.trending],
        popular=[PopularOut(**p.__dict__) for p in e.popular],
        ipos=[IpoOut(name=i.name, sport=i.sport, position=i.position, note=i.note, list_date=str(i.list_date), ipo_price=i.ipo_price, status=i.status, instrument_id=i.instrument_id) for i in e.ipos],
    )
