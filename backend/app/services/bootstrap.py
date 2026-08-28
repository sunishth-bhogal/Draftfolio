"""Small helpers to create users/instruments/portfolios and fund a portfolio.

Funding writes a ``FUND`` transaction leg and updates the cash cache, so even the
starting $100k grant flows through the append-only ledger rather than being a
magic column value.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime

from app.models import (
    CashBalance,
    Instrument,
    Portfolio,
    SignalEvent,
    Transaction,
    User,
)


def create_user(db: Session, *, email: str, display_name: str) -> User:
    user = User(email=email, display_name=display_name)
    db.add(user)
    db.commit()
    return user


def create_instrument(
    db: Session, *, symbol: str, name: str, currency: str, sector: str | None = None
) -> Instrument:
    inst = Instrument(symbol=symbol, name=name, currency=currency, sector=sector)
    db.add(inst)
    db.commit()
    return inst


def create_portfolio(
    db: Session, *, user_id: uuid.UUID, name: str, base_currency: str = "CAD"
) -> Portfolio:
    pf = Portfolio(user_id=user_id, name=name, base_currency=base_currency)
    db.add(pf)
    db.commit()
    return pf


def fund_portfolio(
    db: Session, *, portfolio_id: uuid.UUID, amount: Decimal, currency: str
) -> None:
    cb = db.get(CashBalance, {"portfolio_id": portfolio_id, "currency": currency})
    if cb is None:
        cb = CashBalance(portfolio_id=portfolio_id, currency=currency, amount=Decimal("0"))
        db.add(cb)
    cb.amount = Decimal(cb.amount) + amount
    db.add(
        Transaction(
            portfolio_id=portfolio_id,
            order_id=None,
            account=f"CASH:{currency}",
            cash_delta=amount,
            cash_currency=currency,
        )
    )
    db.commit()


def create_signal(
    db: Session,
    *,
    instrument_id: uuid.UUID | None,
    ts: datetime,
    source: str,
    signal_type: str,
    value: float,
    confidence: float,
    headline: str,
    source_url: str | None = None,
) -> SignalEvent:
    sig = SignalEvent(
        instrument_id=instrument_id,
        ts=ts,
        source=source,
        signal_type=signal_type,
        value=value,
        confidence=confidence,
        headline=headline,
        source_url=source_url,
    )
    db.add(sig)
    db.commit()
    return sig
