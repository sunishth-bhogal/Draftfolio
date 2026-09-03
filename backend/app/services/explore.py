"""Explore / discovery — trending movers, most-held, and upcoming IPOs."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

TREND_WINDOW = 6  # recent price points to measure form over
MIN_TREND_PRICE = 250  # only surface rotation-level players, not small-sample scrubs


@dataclass
class MoverRow:
    instrument_id: str
    name: str
    sport: str | None
    team: str | None
    position: str | None
    headshot_url: str | None
    price: float
    change: float  # over the recent window


@dataclass
class PopularRow:
    instrument_id: str
    name: str
    sport: str | None
    headshot_url: str | None
    price: float
    holders: int


@dataclass
class Explore:
    trending: list[MoverRow] = field(default_factory=list)
    popular: list[PopularRow] = field(default_factory=list)
    ipos: list = field(default_factory=list)  # ipo.IpoOut


def trending(db: Session, top: int = 8) -> list[MoverRow]:
    rows = db.execute(
        text(
            """
            WITH ranked AS (
              SELECT pb.instrument_id, pb.close, pb.bar_date,
                     ROW_NUMBER() OVER (PARTITION BY pb.instrument_id ORDER BY pb.bar_date DESC) AS rn
              FROM price_bars pb
              JOIN instruments i ON i.id = pb.instrument_id
              WHERE pb.source = 'espn' AND i.asset_class = 'PLAYER'
            )
            SELECT r.instrument_id, r.close, r.rn,
                   i.name, i.sport, i.team, i.position, i.headshot_url
            FROM ranked r JOIN instruments i ON i.id = r.instrument_id
            WHERE r.rn <= :w
            """
        ),
        {"w": TREND_WINDOW},
    ).fetchall()

    by_id: dict[str, list] = {}
    for row in rows:
        by_id.setdefault(str(row.instrument_id), []).append(row)

    movers: list[MoverRow] = []
    for _iid, group in by_id.items():
        group.sort(key=lambda x: x.rn)  # rn=1 latest
        if len(group) < 2:
            continue
        latest = float(group[0].close)
        base = float(group[-1].close)
        if base <= 0 or latest < MIN_TREND_PRICE:
            continue
        meta = group[0]
        movers.append(
            MoverRow(
                instrument_id=str(meta.instrument_id),
                name=meta.name,
                sport=meta.sport,
                team=meta.team,
                position=meta.position,
                headshot_url=meta.headshot_url,
                price=latest,
                change=latest / base - 1.0,
            )
        )
    movers.sort(key=lambda m: m.change, reverse=True)
    return movers[:top]


def popular(db: Session, top: int = 8) -> list[PopularRow]:
    rows = db.execute(
        text(
            """
            SELECT i.id, i.name, i.sport, i.headshot_url,
                   COUNT(*) AS holders,
                   (SELECT pb.close FROM price_bars pb
                    WHERE pb.instrument_id = i.id
                    ORDER BY pb.bar_date DESC LIMIT 1) AS price
            FROM positions p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE p.quantity > 0
            GROUP BY i.id, i.name, i.sport, i.headshot_url
            ORDER BY holders DESC, price DESC NULLS LAST
            LIMIT :top
            """
        ),
        {"top": top},
    ).fetchall()
    return [
        PopularRow(
            instrument_id=str(r.id),
            name=r.name,
            sport=r.sport,
            headshot_url=r.headshot_url,
            price=float(r.price) if r.price is not None else 0.0,
            holders=int(r.holders),
        )
        for r in rows
    ]


def explore(db: Session) -> Explore:
    from app.services.ipo import list_ipos

    return Explore(trending=trending(db), popular=popular(db), ipos=list_ipos(db))
