"""Entrypoint for the daily snapshot job (run via cron / Render Cron Job).

    DATABASE_URL=... python -m scripts.snapshot_daily

Set DRAFTFOLIO_PRICE_SOURCE=stooq to pull real closes; otherwise the last known
mark is carried forward.
"""

from __future__ import annotations

import os

from app.db import SessionLocal
from app.services.prices import StooqProvider
from app.services.snapshot_job import run_daily_snapshots

# Stooq uses suffixed symbols; map our tickers here as the catalog grows.
STOOQ_SYMBOL_MAP = {
    "AAPL": "aapl.us",
    "SHOP": "shop.us",
    # Canadian listings differ on Stooq; extend as needed.
}


def main() -> None:
    provider = None
    if os.getenv("DRAFTFOLIO_PRICE_SOURCE", "").lower() == "stooq":
        provider = StooqProvider(symbol_map=STOOQ_SYMBOL_MAP)

    db = SessionLocal()
    try:
        result = run_daily_snapshots(db, provider=provider)
    finally:
        db.close()
    print(
        f"[{result.as_of_date}] prices={result.prices_written} "
        f"(carried_forward={result.prices_carried_forward}) "
        f"snapshots={result.snapshots_written}"
    )


if __name__ == "__main__":
    main()
