"""Order + portfolio endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.ledger import InsufficientCash, InsufficientShares
from app.models import CashBalance, Instrument, Portfolio, Position
from app.schemas.orders import (
    CashBalanceOut,
    OrderRequest,
    OrderResponse,
    PortfolioState,
    PositionOut,
)
from app.services import orders as order_service

router = APIRouter()


@router.post("/portfolios/{portfolio_id}/orders", response_model=OrderResponse)
def place_order(
    portfolio_id: uuid.UUID,
    body: OrderRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        result = order_service.place_order(
            db,
            portfolio_id=portfolio_id,
            idempotency_key=idempotency_key,
            side=body.side,
            symbol=body.symbol,
            quantity=body.quantity,
            price=body.price,
            currency=body.currency,
            fee=body.fee,
        )
    except order_service.PortfolioNotFound:
        raise HTTPException(status_code=404, detail="portfolio not found")
    except order_service.InstrumentNotFound:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {body.symbol}")
    except (InsufficientCash, InsufficientShares) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # 201 for a freshly created order, 200 when replaying an idempotent retry.
    response.status_code = 201 if result.created else 200
    return OrderResponse.model_validate(result.order)


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioState)
def get_portfolio(
    portfolio_id: uuid.UUID, db: Session = Depends(get_db)
) -> PortfolioState:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")

    cash = [
        CashBalanceOut(currency=cb.currency, amount=cb.amount)
        for cb in db.scalars(
            select(CashBalance).where(CashBalance.portfolio_id == portfolio_id)
        )
    ]
    positions = [
        PositionOut(symbol=inst.symbol, quantity=pos.quantity)
        for pos, inst in db.execute(
            select(Position, Instrument)
            .join(Instrument, Position.instrument_id == Instrument.id)
            .where(Position.portfolio_id == portfolio_id)
        )
        if pos.quantity != 0
    ]
    return PortfolioState(
        portfolio_id=portfolio_id,
        base_currency=portfolio.base_currency,
        cash=cash,
        positions=positions,
    )
