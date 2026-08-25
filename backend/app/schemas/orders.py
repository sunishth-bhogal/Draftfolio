"""Request/response models for the order and portfolio endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderRequest(BaseModel):
    side: Literal["BUY", "SELL"]
    symbol: str
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    currency: str = "CAD"
    fee: Decimal = Field(default=Decimal("0"), ge=0)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    side: str
    instrument_id: uuid.UUID
    quantity: Decimal
    price: Decimal
    currency: str
    fee: Decimal
    status: str


class CashBalanceOut(BaseModel):
    currency: str
    amount: Decimal


class PositionOut(BaseModel):
    symbol: str
    quantity: Decimal


class PortfolioState(BaseModel):
    portfolio_id: uuid.UUID
    base_currency: str
    cash: list[CashBalanceOut]
    positions: list[PositionOut]
