"""Catalog + portfolio-create endpoints for the frontend."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import date as _date

from app.db import get_db
from app.models import Instrument, PriceBar, Portfolio, User
from app.services import bootstrap
from app.services import player_analysis
from app.services.valuation import latest_close

router = APIRouter()

DEMO_EMAIL = "demo@draftfolio.io"


class PortfolioListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_currency: str


class InstrumentOut(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    sector: str | None
    last_price: float | None
    asset_class: str
    sport: str | None
    team: str | None
    position: str | None
    headshot_url: str | None


class CreatePortfolioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_currency: str = "CAD"
    starting_cash: Decimal = Field(default=Decimal("100000"), gt=0)


@router.get("/portfolios", response_model=list[PortfolioListItem])
def list_portfolios(db: Session = Depends(get_db)) -> list[PortfolioListItem]:
    return list(db.scalars(select(Portfolio).order_by(Portfolio.name)))


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(db: Session = Depends(get_db)) -> list[InstrumentOut]:
    now = datetime.now(timezone.utc)
    out: list[InstrumentOut] = []
    for inst in db.scalars(select(Instrument).order_by(Instrument.symbol)):
        price = latest_close(db, inst.id, now)
        out.append(
            InstrumentOut(
                id=inst.id,
                symbol=inst.symbol,
                name=inst.name,
                currency=inst.currency,
                sector=inst.sector,
                last_price=float(price) if price is not None else None,
                asset_class=inst.asset_class,
                sport=inst.sport,
                team=inst.team,
                position=inst.position,
                headshot_url=inst.headshot_url,
            )
        )
    return out


@router.post("/portfolios", response_model=PortfolioListItem, status_code=201)
def create_portfolio(
    body: CreatePortfolioRequest, db: Session = Depends(get_db)
) -> PortfolioListItem:
    """Create a portfolio for the demo user and fund it with virtual cash.

    Single-tenant for now: all portfolios belong to one implicit demo user until
    auth lands. Funding flows through the ledger as a FUND transaction.
    """
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = bootstrap.create_user(db, email=DEMO_EMAIL, display_name="Demo User")

    pf = bootstrap.create_portfolio(
        db, user_id=user.id, name=body.name, base_currency=body.base_currency
    )
    bootstrap.fund_portfolio(
        db, portfolio_id=pf.id, amount=body.starting_cash, currency=body.base_currency
    )
    return pf


class PricePoint(BaseModel):
    date: _date
    close: float
    formula_version: str | None


@router.get("/instruments/{instrument_id}/history", response_model=list[PricePoint])
def price_history(instrument_id: uuid.UUID, db: Session = Depends(get_db)) -> list[PricePoint]:
    rows = db.scalars(
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument_id)
        .order_by(PriceBar.bar_date.asc())
    )
    return [
        PricePoint(date=r.bar_date, close=float(r.close), formula_version=r.formula_version)
        for r in rows
    ]


class BreakdownOut(BaseModel):
    available: bool
    games: int = 0
    formula_version: str | None = None
    averages: dict[str, float] = {}
    components: dict[str, float] = {}
    base_value: float = 0.0
    form_multiplier: float = 1.0
    form_adjustment: float = 0.0
    final_value: float = 0.0


@router.get("/instruments/{instrument_id}/breakdown", response_model=BreakdownOut)
def value_breakdown(instrument_id: uuid.UUID, db: Session = Depends(get_db)) -> BreakdownOut:
    b = player_analysis.value_breakdown_for(db, instrument_id)
    return BreakdownOut(**b.__dict__)


class ValidationRowOut(BaseModel):
    name: str
    value: float
    ppg: float
    production: float
    games: int


class ValidationOut(BaseModel):
    num_players: int
    corr_value_production: float | None
    corr_value_minutes: float | None
    min_games: int
    top: list[ValidationRowOut]
    watchouts: list[ValidationRowOut]


@router.get("/methodology/validation", response_model=ValidationOut)
def methodology_validation(db: Session = Depends(get_db)) -> ValidationOut:
    v = player_analysis.league_validation(db)
    return ValidationOut(
        num_players=v.num_players,
        corr_value_production=v.corr_value_production,
        corr_value_minutes=v.corr_value_minutes,
        min_games=v.min_games,
        top=[ValidationRowOut(**r.__dict__) for r in v.top],
        watchouts=[ValidationRowOut(**r.__dict__) for r in v.watchouts],
    )
