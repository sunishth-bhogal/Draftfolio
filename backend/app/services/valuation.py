"""Portfolio valuation, snapshots, and returns.

Valuation is **point-in-time**: the latest close used for each holding is the
most recent bar whose ``as_of`` is at or before the valuation time. This is what
keeps a historical replay honest — it can never read a price that wasn't known
yet.

FX is deferred (ADR: Phase 3). Holdings whose currency differs from the
portfolio's base currency are reported separately as ``fx_pending`` rather than
silently converted, so equity is never quietly wrong.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CashBalance,
    Instrument,
    PortfolioSnapshot,
    Position,
    PriceBar,
)


@dataclass
class Holding:
    symbol: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    weight: Decimal  # fraction of equity


@dataclass
class Valuation:
    as_of: datetime
    base_currency: str
    cash: Decimal
    market_value: Decimal
    equity: Decimal
    holdings: list[Holding] = field(default_factory=list)
    fx_pending: list[str] = field(default_factory=list)  # symbols needing FX
    unpriced: list[str] = field(default_factory=list)  # no bar available yet


def latest_close(
    db: Session, instrument_id: uuid.UUID, as_of: datetime
) -> Decimal | None:
    """Most recent close known as of ``as_of`` (look-ahead safe)."""
    row = db.scalar(
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument_id, PriceBar.as_of <= as_of)
        .order_by(PriceBar.bar_date.desc())
        .limit(1)
    )
    return Decimal(row.close) if row is not None else None


def value_portfolio(
    db: Session, portfolio_id: uuid.UUID, base_currency: str, as_of: datetime | None = None
) -> Valuation:
    as_of = as_of or datetime.now(timezone.utc)

    cash = sum(
        (
            Decimal(cb.amount)
            for cb in db.scalars(
                select(CashBalance).where(
                    CashBalance.portfolio_id == portfolio_id,
                    CashBalance.currency == base_currency,
                )
            )
        ),
        Decimal("0"),
    )

    holdings: list[Holding] = []
    fx_pending: list[str] = []
    unpriced: list[str] = []
    market_value = Decimal("0")

    rows = db.execute(
        select(Position, Instrument)
        .join(Instrument, Position.instrument_id == Instrument.id)
        .where(Position.portfolio_id == portfolio_id)
    )
    for pos, inst in rows:
        qty = Decimal(pos.quantity)
        if qty == 0:
            continue
        if inst.currency != base_currency:
            fx_pending.append(inst.symbol)
            continue
        price = latest_close(db, inst.id, as_of)
        if price is None:
            unpriced.append(inst.symbol)
            continue
        mv = (qty * price).quantize(Decimal("0.0001"))
        market_value += mv
        holdings.append(Holding(inst.symbol, qty, price, mv, Decimal("0")))

    equity = (cash + market_value).quantize(Decimal("0.0001"))
    # Fill in weights now that we know equity.
    for h in holdings:
        h.weight = (h.market_value / equity).quantize(Decimal("0.0001")) if equity else Decimal("0")

    return Valuation(
        as_of=as_of,
        base_currency=base_currency,
        cash=cash.quantize(Decimal("0.0001")),
        market_value=market_value.quantize(Decimal("0.0001")),
        equity=equity,
        holdings=sorted(holdings, key=lambda h: h.market_value, reverse=True),
        fx_pending=fx_pending,
        unpriced=unpriced,
    )


def take_snapshot(
    db: Session,
    portfolio_id: uuid.UUID,
    base_currency: str,
    snapshot_date: date,
    as_of: datetime | None = None,
) -> PortfolioSnapshot:
    """Write (or update) the daily snapshot for a portfolio."""
    val = value_portfolio(db, portfolio_id, base_currency, as_of=as_of)
    snap = db.scalar(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.portfolio_id == portfolio_id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
    )
    if snap is None:
        snap = PortfolioSnapshot(portfolio_id=portfolio_id, snapshot_date=snapshot_date)
        db.add(snap)
    snap.cash = val.cash
    snap.market_value = val.market_value
    snap.equity = val.equity
    db.commit()
    return snap


@dataclass
class ReturnPoint:
    snapshot_date: date
    equity: Decimal
    daily_return: Decimal | None
    cumulative_return: Decimal | None


def return_series(db: Session, portfolio_id: uuid.UUID) -> list[ReturnPoint]:
    """Derive daily and cumulative returns from the snapshot series."""
    snaps = list(
        db.scalars(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
    )
    points: list[ReturnPoint] = []
    base = Decimal(snaps[0].equity) if snaps else None
    prev: Decimal | None = None
    for s in snaps:
        eq = Decimal(s.equity)
        daily = (eq / prev - 1) if prev and prev != 0 else None
        cumulative = (eq / base - 1) if base and base != 0 else None
        points.append(
            ReturnPoint(
                snapshot_date=s.snapshot_date,
                equity=eq,
                daily_return=daily.quantize(Decimal("0.000001")) if daily is not None else None,
                cumulative_return=(
                    cumulative.quantize(Decimal("0.000001")) if cumulative is not None else None
                ),
            )
        )
        prev = eq
    return points
