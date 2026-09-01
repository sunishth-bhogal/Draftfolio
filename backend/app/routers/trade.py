"""Market trading — buy/sell any instrument at its current price, for your team."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.ledger import InsufficientCash, InsufficientShares
from app.models import Instrument, Portfolio, User
from app.services import auth as auth_svc
from app.services import orders as order_service
from app.services.valuation import latest_close


class TradeRequest(BaseModel):
    instrument_id: uuid.UUID
    side: str  # BUY | SELL
    shares: Decimal = Field(gt=0)


class TradeResult(BaseModel):
    ok: bool
    side: str
    shares: float
    price: float
    cash: float
    shares_held: float


router = APIRouter()


@router.post("/trade", response_model=TradeResult)
def trade(
    body: TradeRequest,
    user: User = Depends(auth_svc.current_user),
    db: Session = Depends(get_db),
) -> TradeResult:
    if body.side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")

    pf = db.scalar(select(Portfolio).where(Portfolio.user_id == user.id).limit(1))
    if pf is None:
        raise HTTPException(status_code=404, detail="no team")

    inst = db.get(Instrument, body.instrument_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="unknown instrument")

    price = latest_close(db, inst.id, datetime.now(timezone.utc))
    if price is None:
        raise HTTPException(status_code=422, detail="no market price for this asset")

    try:
        order_service.place_order(
            db,
            portfolio_id=pf.id,
            idempotency_key=str(uuid.uuid4()),  # each market order is distinct
            side=body.side,
            symbol=inst.symbol,
            quantity=body.shares,
            price=Decimal(price),
            currency=pf.base_currency,
            fee=Decimal("0"),
        )
    except (InsufficientCash, InsufficientShares) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Report resulting cash + holding.
    from app.models import CashBalance, Position

    cb = db.get(CashBalance, {"portfolio_id": pf.id, "currency": pf.base_currency})
    pos = db.get(Position, {"portfolio_id": pf.id, "instrument_id": inst.id})
    return TradeResult(
        ok=True,
        side=body.side,
        shares=float(body.shares),
        price=float(price),
        cash=float(cb.amount) if cb else 0.0,
        shares_held=float(pos.quantity) if pos else 0.0,
    )
