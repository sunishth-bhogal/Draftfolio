"""ORM tables — the persistence shell around the pure ledger domain.

Mirrors the four-table decision in DESIGN.md:
  * ``orders``        — what the user requested (immutable)
  * ``transactions``  — what executed (append-only ledger, source of truth)
  * ``positions`` / ``cash_balances`` — derived caches of the folded log
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Money4, Qty8


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    asset_class: Mapped[str] = mapped_column(String(20), default="EQUITY")
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    base_currency: Mapped[str] = mapped_column(String(3), default="CAD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Order(Base):
    """What the user requested. Immutable once written.

    The ``(portfolio_id, idempotency_key)`` unique constraint is the database-level
    guarantee behind idempotent order processing: a retried request can insert at
    most one row.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "idempotency_key", name="uq_orders_portfolio_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    side: Mapped[str] = mapped_column(String(4))  # BUY / SELL
    instrument_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"))
    quantity: Mapped[object] = mapped_column(Qty8)
    price: Mapped[object] = mapped_column(Money4)
    currency: Mapped[str] = mapped_column(String(3))
    fee: Mapped[object] = mapped_column(Money4)
    status: Mapped[str] = mapped_column(String(12), default="FILLED")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Transaction(Base):
    """Append-only ledger leg. Never updated or deleted."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    account: Mapped[str] = mapped_column(String(60))  # CASH:CAD or POSITION:AAPL
    cash_delta: Mapped[object | None] = mapped_column(Money4, nullable=True)
    cash_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    quantity_delta: Mapped[object | None] = mapped_column(Qty8, nullable=True)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("instruments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Position(Base):
    """Derived cache: current share quantity per instrument."""

    __tablename__ = "positions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), primary_key=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id"), primary_key=True
    )
    quantity: Mapped[object] = mapped_column(Qty8, default=0)

    instrument: Mapped[Instrument] = relationship()


class CashBalance(Base):
    """Derived cache: current cash per currency."""

    __tablename__ = "cash_balances"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), primary_key=True
    )
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    amount: Mapped[object] = mapped_column(Money4, default=0)
