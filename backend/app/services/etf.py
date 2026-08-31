"""Player-index ETFs — baskets of players priced from the underlying.

An ETF is an Instrument (asset_class='ETF') with a set of constituent players.
Its price on any date is the weighted mean of its constituents' most recent
values on/before that date (carry-forward), so it earns a real, backfilled
history from the players it holds — a sports index fund.
"""

from __future__ import annotations

import uuid
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EtfConstituent, Instrument, PriceBar

CURRENCY = "CAD"
INDEX_VERSION = "index-v1"


def define_etf(
    db: Session,
    *,
    symbol: str,
    name: str,
    sport: str,
    members: list[Instrument],
    weights: list[float] | None = None,
) -> Instrument:
    """Create/replace an ETF instrument and its constituent set."""
    etf = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if etf is None:
        etf = Instrument(symbol=symbol, currency=CURRENCY, asset_class="ETF")
        db.add(etf)
    etf.name = name
    etf.sport = sport
    etf.sector = "Index"
    db.flush()

    db.query(EtfConstituent).filter(EtfConstituent.etf_id == etf.id).delete()
    ws = weights or [1.0] * len(members)
    for m, w in zip(members, ws):
        db.add(EtfConstituent(etf_id=etf.id, member_id=m.id, weight=w))
    db.commit()
    return etf


def _member_series(db: Session, member_id: uuid.UUID) -> tuple[list[date], list[float]]:
    bars = list(
        db.scalars(
            select(PriceBar)
            .where(PriceBar.instrument_id == member_id, PriceBar.source == "espn")
            .order_by(PriceBar.bar_date.asc())
        )
    )
    return [b.bar_date for b in bars], [float(b.close) for b in bars]


def backfill_etf(db: Session, etf: Instrument) -> int:
    """Compute the ETF's price history as the weighted basket of constituents."""
    cons = list(db.scalars(select(EtfConstituent).where(EtfConstituent.etf_id == etf.id)))
    series = {c.member_id: _member_series(db, c.member_id) for c in cons}
    weights = {c.member_id: c.weight for c in cons}

    all_dates = sorted({d for dates, _ in series.values() for d in dates})
    if not all_dates:
        return 0

    written = 0
    for d in all_dates:
        num = 0.0
        wsum = 0.0
        for mid, (dates, closes) in series.items():
            i = bisect_right(dates, d) - 1  # latest bar on/before d (carry-forward)
            if i < 0:
                continue
            num += weights[mid] * closes[i]
            wsum += weights[mid]
        if wsum == 0:
            continue
        value = round(num / wsum, 2)
        _write_bar(db, etf, d, value)
        written += 1
    db.commit()
    return written


def _write_bar(db: Session, etf: Instrument, bar_date: date, value: float) -> None:
    existing = db.scalar(
        select(PriceBar).where(
            PriceBar.instrument_id == etf.id,
            PriceBar.bar_date == bar_date,
            PriceBar.source == "etf",
        )
    )
    bar = existing or PriceBar(instrument_id=etf.id, bar_date=bar_date, source="etf")
    bar.close = Decimal(str(value))
    bar.currency = CURRENCY
    bar.formula_version = INDEX_VERSION
    bar.as_of = datetime.combine(
        bar_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )
    if existing is None:
        db.add(bar)
    db.flush()


@dataclass
class Constituent:
    symbol: str
    name: str
    member_id: uuid.UUID
    value: float | None
    weight_pct: float


@dataclass
class Composition:
    available: bool
    count: int = 0
    constituents: list[Constituent] = None  # type: ignore


def etf_composition(db: Session, etf_id: uuid.UUID, top: int = 12) -> Composition:
    from app.services.valuation import latest_close

    cons = list(db.scalars(select(EtfConstituent).where(EtfConstituent.etf_id == etf_id)))
    if not cons:
        return Composition(available=False)
    now = datetime.now(timezone.utc)
    rows: list[Constituent] = []
    total_w = sum(c.weight for c in cons) or 1.0
    for c in cons:
        inst = db.get(Instrument, c.member_id)
        price = latest_close(db, c.member_id, now)
        rows.append(
            Constituent(
                symbol=inst.symbol,
                name=inst.name,
                member_id=c.member_id,
                value=float(price) if price is not None else None,
                weight_pct=round(c.weight / total_w * 100, 2),
            )
        )
    rows.sort(key=lambda r: (r.value or 0), reverse=True)
    return Composition(available=True, count=len(rows), constituents=rows[:top])
