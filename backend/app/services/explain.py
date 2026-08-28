"""'Why did my portfolio move?' — a deterministic, auditable explainer.

Not an LLM guess. It (1) measures each holding's actual dollar contribution to
the latest daily move by folding real prices, (2) ranks holdings by that
contribution, and (3) left-joins recent ``signal_events`` for the top movers in
the same time window — each surfaced with its source link and an explicit
*correlation, not causation* caveat.

Assumes holdings were unchanged over the one-day window (true for the current
buy-and-hold model); intraday trades would need per-trade attribution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, PortfolioSnapshot, Position, SignalEvent
from app.services.valuation import close_asof_date

CAVEAT = "Signals are correlated context, not proven causes of the price move."


@dataclass
class SignalOut:
    source: str
    signal_type: str
    value: float
    confidence: float
    headline: str
    source_url: str | None


@dataclass
class Driver:
    symbol: str
    dollar_pnl: Decimal
    contribution: float  # fraction of prior equity (signed)
    price_change: float  # asset return over the window (signed)
    signals: list[SignalOut] = field(default_factory=list)


@dataclass
class MoveExplanation:
    available: bool
    as_of_date: object | None = None
    prev_date: object | None = None
    portfolio_return: float | None = None
    prev_equity: Decimal | None = None
    latest_equity: Decimal | None = None
    drivers: list[Driver] = field(default_factory=list)
    note: str = CAVEAT
    reason: str | None = None  # why unavailable


def _recent_signals(
    db: Session, instrument_id: uuid.UUID, start: datetime, end: datetime, limit: int = 3
) -> list[SignalOut]:
    rows = db.scalars(
        select(SignalEvent)
        .where(
            SignalEvent.instrument_id == instrument_id,
            SignalEvent.ts >= start,
            SignalEvent.ts <= end,
        )
        .order_by(SignalEvent.confidence.desc(), SignalEvent.ts.desc())
        .limit(limit)
    )
    return [
        SignalOut(
            source=s.source,
            signal_type=s.signal_type,
            value=s.value,
            confidence=s.confidence,
            headline=s.headline,
            source_url=s.source_url,
        )
        for s in rows
    ]


def explain_move(
    db: Session, portfolio_id: uuid.UUID, top_n: int = 4
) -> MoveExplanation:
    now = datetime.now(timezone.utc)

    # Need the two most recent snapshots to define the move window.
    snaps = list(
        db.scalars(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioSnapshot.snapshot_date.desc())
            .limit(2)
        )
    )
    if len(snaps) < 2:
        return MoveExplanation(available=False, reason="need at least two daily snapshots")

    latest, prev = snaps[0], snaps[1]
    prev_equity = Decimal(prev.equity)
    latest_equity = Decimal(latest.equity)
    if prev_equity == 0:
        return MoveExplanation(available=False, reason="prior equity is zero")

    portfolio_return = float((latest_equity - prev_equity) / prev_equity)

    # Signal window: from the prior snapshot day to now.
    window_start = datetime.combine(prev.snapshot_date, datetime.min.time(), tzinfo=timezone.utc)

    drivers: list[Driver] = []
    for pos, inst in db.execute(
        select(Position, Instrument)
        .join(Instrument, Position.instrument_id == Instrument.id)
        .where(Position.portfolio_id == portfolio_id)
    ):
        qty = Decimal(pos.quantity)
        if qty == 0:
            continue
        p_prev = close_asof_date(db, inst.id, prev.snapshot_date, now)
        p_latest = close_asof_date(db, inst.id, latest.snapshot_date, now)
        if p_prev is None or p_latest is None:
            continue
        dollar_pnl = (qty * (p_latest - p_prev)).quantize(Decimal("0.01"))
        contribution = float(dollar_pnl / prev_equity)
        price_change = float((p_latest - p_prev) / p_prev) if p_prev != 0 else 0.0
        drivers.append(
            Driver(
                symbol=inst.symbol,
                dollar_pnl=dollar_pnl,
                contribution=contribution,
                price_change=price_change,
                signals=_recent_signals(db, inst.id, window_start, now),
            )
        )

    # Rank by absolute impact; keep the biggest movers.
    drivers.sort(key=lambda d: abs(d.contribution), reverse=True)

    return MoveExplanation(
        available=True,
        as_of_date=latest.snapshot_date,
        prev_date=prev.snapshot_date,
        portfolio_return=portfolio_return,
        prev_equity=prev_equity,
        latest_equity=latest_equity,
        drivers=drivers[:top_n],
    )
