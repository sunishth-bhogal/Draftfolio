"""Valuation, snapshot, and returns endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Portfolio
from app.services import analytics as analytics_service
from app.services import explain as explain_service
from app.services import valuation as val_service

router = APIRouter()


class HoldingOut(BaseModel):
    instrument_id: uuid.UUID
    symbol: str
    name: str
    quantity: float
    price: float
    market_value: float
    weight: float
    day_change: float | None = None


class ValuationOut(BaseModel):
    as_of: str
    base_currency: str
    cash: float
    market_value: float
    equity: float
    holdings: list[HoldingOut]
    fx_pending: list[str]
    unpriced: list[str]


class SnapshotOut(BaseModel):
    snapshot_date: date
    cash: float
    market_value: float
    equity: float


class ReturnPointOut(BaseModel):
    snapshot_date: date
    equity: float
    daily_return: float | None
    cumulative_return: float | None


class AnalyticsOut(BaseModel):
    periods: int
    cumulative_return: float | None
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    benchmark: str | None
    benchmark_return: float | None
    beta: float | None
    alpha: float | None
    tracking_error: float | None
    hhi: float | None
    effective_holdings: float | None
    notes: list[str]


def _load(db: Session, portfolio_id: uuid.UUID) -> Portfolio:
    pf = db.get(Portfolio, portfolio_id)
    if pf is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return pf


@router.get("/portfolios/{portfolio_id}/valuation", response_model=ValuationOut)
def get_valuation(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> ValuationOut:
    pf = _load(db, portfolio_id)
    v = val_service.value_portfolio(db, portfolio_id, pf.base_currency)
    return ValuationOut(
        as_of=v.as_of.isoformat(),
        base_currency=v.base_currency,
        cash=float(v.cash),
        market_value=float(v.market_value),
        equity=float(v.equity),
        holdings=[
            HoldingOut(
                instrument_id=h.instrument_id,
                symbol=h.symbol,
                name=h.name,
                quantity=float(h.quantity),
                price=float(h.price),
                market_value=float(h.market_value),
                weight=float(h.weight),
                day_change=float(h.day_change) if h.day_change is not None else None,
            )
            for h in v.holdings
        ],
        fx_pending=v.fx_pending,
        unpriced=v.unpriced,
    )


@router.post("/portfolios/{portfolio_id}/snapshots", response_model=SnapshotOut)
def create_snapshot(
    portfolio_id: uuid.UUID,
    snapshot_date: date | None = None,
    db: Session = Depends(get_db),
) -> SnapshotOut:
    pf = _load(db, portfolio_id)
    snap = val_service.take_snapshot(
        db, portfolio_id, pf.base_currency, snapshot_date or date.today()
    )
    return SnapshotOut(
        snapshot_date=snap.snapshot_date,
        cash=float(snap.cash),
        market_value=float(snap.market_value),
        equity=float(snap.equity),
    )


@router.get("/portfolios/{portfolio_id}/returns", response_model=list[ReturnPointOut])
def get_returns(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReturnPointOut]:
    _load(db, portfolio_id)
    return [
        ReturnPointOut(
            snapshot_date=p.snapshot_date,
            equity=float(p.equity),
            daily_return=float(p.daily_return) if p.daily_return is not None else None,
            cumulative_return=(
                float(p.cumulative_return) if p.cumulative_return is not None else None
            ),
        )
        for p in val_service.return_series(db, portfolio_id)
    ]


class SignalItem(BaseModel):
    source: str
    signal_type: str
    value: float
    confidence: float
    headline: str
    source_url: str | None


class DriverItem(BaseModel):
    symbol: str
    dollar_pnl: float
    contribution: float
    price_change: float
    signals: list[SignalItem]


class ExplainOut(BaseModel):
    available: bool
    reason: str | None = None
    as_of_date: date | None = None
    prev_date: date | None = None
    portfolio_return: float | None = None
    prev_equity: float | None = None
    latest_equity: float | None = None
    note: str | None = None
    drivers: list[DriverItem] = []


@router.get("/portfolios/{portfolio_id}/explain", response_model=ExplainOut)
def explain_move(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> ExplainOut:
    _load(db, portfolio_id)
    e = explain_service.explain_move(db, portfolio_id)
    if not e.available:
        return ExplainOut(available=False, reason=e.reason)
    return ExplainOut(
        available=True,
        as_of_date=e.as_of_date,
        prev_date=e.prev_date,
        portfolio_return=e.portfolio_return,
        prev_equity=float(e.prev_equity) if e.prev_equity is not None else None,
        latest_equity=float(e.latest_equity) if e.latest_equity is not None else None,
        note=e.note,
        drivers=[
            DriverItem(
                symbol=d.symbol,
                dollar_pnl=float(d.dollar_pnl),
                contribution=d.contribution,
                price_change=d.price_change,
                signals=[
                    SignalItem(
                        source=s.source,
                        signal_type=s.signal_type,
                        value=s.value,
                        confidence=s.confidence,
                        headline=s.headline,
                        source_url=s.source_url,
                    )
                    for s in d.signals
                ],
            )
            for d in e.drivers
        ],
    )


@router.get("/portfolios/{portfolio_id}/analytics", response_model=AnalyticsOut)
def get_analytics(
    portfolio_id: uuid.UUID,
    benchmark: str | None = None,
    rf: float = 0.0,
    db: Session = Depends(get_db),
) -> AnalyticsOut:
    pf = _load(db, portfolio_id)
    a = analytics_service.portfolio_analytics(
        db, portfolio_id, pf.base_currency, benchmark=benchmark, rf_annual=rf
    )
    return AnalyticsOut(**a.__dict__)
