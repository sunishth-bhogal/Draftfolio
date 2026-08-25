"""Price ingestion.

A ``PriceProvider`` is any source of daily closes. ``StooqProvider`` pulls free
CSV end-of-day data (no API key) for real use; ``StaticProvider`` returns
in-memory bars for deterministic, offline tests. Ingestion is idempotent: the
``(instrument, date, source)`` unique constraint means re-running a day's load
updates rather than duplicates.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, PriceBar


@dataclass(frozen=True)
class Bar:
    bar_date: date
    close: Decimal


class PriceProvider(Protocol):
    def daily_closes(self, symbol: str, start: date, end: date) -> list[Bar]: ...


class StaticProvider:
    """Deterministic provider for tests/seeding: symbol -> {date: close}."""

    def __init__(self, data: dict[str, dict[date, Decimal]]):
        self._data = data

    def daily_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        rows = self._data.get(symbol, {})
        return [
            Bar(d, Decimal(str(c)))
            for d, c in sorted(rows.items())
            if start <= d <= end
        ]


class StooqProvider:
    """Free end-of-day CSV from stooq.com. Network required; used outside tests.

    Stooq symbols differ from tickers (US equities use a ``.us`` suffix, e.g.
    ``aapl.us``). ``symbol_map`` lets callers translate.
    """

    URL = "https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"

    def __init__(self, symbol_map: dict[str, str] | None = None, timeout: int = 15):
        self._map = symbol_map or {}
        self._timeout = timeout

    def daily_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        s = self._map.get(symbol, symbol).lower()
        url = self.URL.format(
            symbol=s, d1=start.strftime("%Y%m%d"), d2=end.strftime("%Y%m%d")
        )
        with urllib.request.urlopen(url, timeout=self._timeout) as resp:
            text = resp.read().decode("utf-8")
        bars: list[Bar] = []
        for row in csv.DictReader(io.StringIO(text)):
            if not row.get("Close") or row["Close"] == "N/A":
                continue
            bars.append(
                Bar(datetime.strptime(row["Date"], "%Y-%m-%d").date(), Decimal(row["Close"]))
            )
        return bars


def ingest(
    db: Session,
    *,
    provider: PriceProvider,
    symbol: str,
    start: date,
    end: date,
    source: str = "seed",
    as_of: datetime | None = None,
) -> int:
    """Load bars for one symbol into ``price_bars``. Returns rows written."""
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if instrument is None:
        raise LookupError(f"unknown symbol: {symbol}")
    as_of = as_of or datetime.now(timezone.utc)

    written = 0
    for bar in provider.daily_closes(symbol, start, end):
        existing = db.scalar(
            select(PriceBar).where(
                PriceBar.instrument_id == instrument.id,
                PriceBar.bar_date == bar.bar_date,
                PriceBar.source == source,
            )
        )
        if existing is None:
            db.add(
                PriceBar(
                    instrument_id=instrument.id,
                    bar_date=bar.bar_date,
                    close=bar.close,
                    currency=instrument.currency,
                    source=source,
                    as_of=as_of,
                )
            )
        else:
            existing.close = bar.close
            existing.as_of = as_of
        written += 1
    db.commit()
    return written


def ingest_bars(
    db: Session,
    *,
    symbol: str,
    bars: Iterable[tuple[date, Decimal | str | float]],
    source: str = "seed",
    as_of: datetime | None = None,
) -> int:
    """Convenience: ingest explicit (date, close) pairs via StaticProvider."""
    data = {symbol: {d: Decimal(str(c)) for d, c in bars}}
    dates = list(data[symbol])
    return ingest(
        db,
        provider=StaticProvider(data),
        symbol=symbol,
        start=min(dates),
        end=max(dates),
        source=source,
        as_of=as_of,
    )
