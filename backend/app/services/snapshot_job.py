"""Daily snapshot job — the process that makes portfolios accrue history.

Once a day it (1) records each instrument's closing mark for the date and
(2) writes a snapshot for every portfolio. Run it on a schedule (Render cron)
and a freshly drafted portfolio starts building the equity curve and risk
metrics that were "n/a" at draft time.

Fully idempotent: prices upsert on ``(instrument, date, source)`` and snapshots
upsert on ``(portfolio, date)``, so re-running for the same day is a no-op.

Price source: pass a ``PriceProvider`` (e.g. Stooq) to pull real closes. Without
one — the default in the free demo — it *carries forward* the last known close,
so the mechanism (history accrual) works even with no live data feed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, Portfolio
from app.services.prices import PriceProvider, ingest_bars
from app.services.valuation import latest_close, take_snapshot


@dataclass
class SnapshotRunResult:
    as_of_date: date
    prices_written: int
    prices_carried_forward: int
    snapshots_written: int


def run_daily_snapshots(
    db: Session,
    *,
    as_of_date: date | None = None,
    provider: PriceProvider | None = None,
) -> SnapshotRunResult:
    as_of_date = as_of_date or date.today()
    now = datetime.now(timezone.utc)
    prices_written = 0
    carried = 0

    for inst in db.scalars(select(Instrument)):
        close = None
        if provider is not None:
            try:
                bars = provider.daily_closes(inst.symbol, as_of_date, as_of_date)
                close = bars[-1].close if bars else None
            except Exception:  # noqa: BLE001 — a flaky feed shouldn't kill the run
                close = None
        if close is None:
            close = latest_close(db, inst.id, now)  # carry forward last known mark
            if close is not None:
                carried += 1
        if close is not None:
            ingest_bars(
                db,
                symbol=inst.symbol,
                bars=[(as_of_date, close)],
                source="daily",
                as_of=now,
            )
            prices_written += 1

    snapshots = 0
    for pf in db.scalars(select(Portfolio)):
        take_snapshot(db, pf.id, pf.base_currency, as_of_date, as_of=now)
        snapshots += 1

    return SnapshotRunResult(
        as_of_date=as_of_date,
        prices_written=prices_written,
        prices_carried_forward=carried,
        snapshots_written=snapshots,
    )
