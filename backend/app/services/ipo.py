"""Timed IPOs — prospects that list on a date and become tradeable.

Before ``list_date`` an IPO is 'upcoming' (a countdown on Explore). On/after it,
``process_listings`` lists it: a real PLAYER instrument is created at the IPO
price, so it shows up in the market and can be bought/sold like any player. This
runs lazily whenever Explore is fetched, so listings happen on schedule with no
cron required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, Ipo, PriceBar

# Curated real 2026 prospects. Some already listed (past date) to show the live
# state; the marquee names list on the 2026-27 season openers.
SEED_IPOS = [
    # name, sport, position, note, list_date, ipo_price
    ("AJ Dybantsa", "NBA", "F", "Consensus #1 college prospect", date(2026, 10, 24), 520),
    ("Darryn Peterson", "NBA", "G", "Elite two-way guard", date(2026, 10, 24), 460),
    ("Cameron Boozer", "NBA", "F", "Dominant frontcourt prospect", date(2026, 10, 24), 440),
    ("Cayden Boozer", "NBA", "G", "Floor general, high feel", date(2026, 10, 24), 300),
    ("Gavin McKenna", "NHL", "LW", "Generational winger, #1 overall buzz", date(2026, 10, 8), 540),
    ("Michael Misa", "NHL", "C", "Dynamic playmaking centre", date(2026, 10, 8), 380),
    # Already listed (past date) — now trading in the demo.
    ("Ace Bailey", "NBA", "F", "Rookie riser, big usage", date(2026, 8, 1), 360),
    ("Ivan Demidov", "NHL", "RW", "Skilled sniper, early call-up", date(2026, 8, 1), 340),
]


def _slug(name: str) -> str:
    return "IPO:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def seed_ipos(db: Session) -> int:
    n = 0
    for name, sport, pos, note, ld, price in SEED_IPOS:
        if db.scalar(select(Ipo).where(Ipo.name == name)) is None:
            db.add(Ipo(name=name, sport=sport, position=pos, note=note, list_date=ld, ipo_price=price))
            n += 1
    db.commit()
    return n


def process_listings(db: Session, today: date | None = None) -> int:
    """List any upcoming IPO whose date has arrived. Idempotent."""
    today = today or date.today()
    due = db.scalars(
        select(Ipo).where(Ipo.status == "upcoming", Ipo.list_date <= today)
    ).all()
    listed = 0
    for ipo in due:
        symbol = _slug(ipo.name)
        inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
        if inst is None:
            inst = Instrument(
                symbol=symbol, name=ipo.name, currency="CAD", asset_class="PLAYER",
                sport=ipo.sport, position=ipo.position, sector=ipo.position,
            )
            db.add(inst)
            db.flush()
            db.add(
                PriceBar(
                    instrument_id=inst.id, bar_date=ipo.list_date,
                    close=Decimal(ipo.ipo_price), currency="CAD", source="ipo",
                    as_of=datetime.combine(ipo.list_date, datetime.min.time(), tzinfo=timezone.utc),
                )
            )
        ipo.instrument_id = inst.id
        ipo.status = "listed"
        listed += 1
    db.commit()
    return listed


@dataclass
class IpoOut:
    name: str
    sport: str
    position: str
    note: str
    list_date: date
    ipo_price: int
    status: str
    instrument_id: str | None


def list_ipos(db: Session, today: date | None = None) -> list[IpoOut]:
    process_listings(db, today)
    rows = db.scalars(select(Ipo).order_by(Ipo.status.desc(), Ipo.list_date.asc())).all()
    return [
        IpoOut(
            name=i.name, sport=i.sport, position=i.position, note=i.note,
            list_date=i.list_date, ipo_price=i.ipo_price, status=i.status,
            instrument_id=str(i.instrument_id) if i.instrument_id else None,
        )
        for i in rows
    ]
