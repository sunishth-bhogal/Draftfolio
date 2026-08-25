"""Read-only list endpoints the frontend needs (portfolios, instruments)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Instrument, Portfolio

router = APIRouter()


class PortfolioListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_currency: str


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    sector: str | None


@router.get("/portfolios", response_model=list[PortfolioListItem])
def list_portfolios(db: Session = Depends(get_db)) -> list[PortfolioListItem]:
    return list(db.scalars(select(Portfolio).order_by(Portfolio.name)))


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(db: Session = Depends(get_db)) -> list[InstrumentOut]:
    return list(db.scalars(select(Instrument).order_by(Instrument.symbol)))
