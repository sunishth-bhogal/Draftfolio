"""Rivals ladder — XP, levels, divisions, and gameweek scoring.

NHL-Fantasy-Stars style: everyone has one team, plays each gameweek, earns XP and
division points from how their portfolio performed relative to rivals in the same
division, and climbs (or drops) divisions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Gameweek, GameweekResult, Portfolio, User
from app.services.valuation import take_snapshot, value_portfolio

DIVISIONS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond"]
XP_PER_LEVEL = 500
PROMOTE_AT = 10  # division points
RELEGATE_AT = -3


def level_for_xp(xp: int) -> int:
    return 1 + xp // XP_PER_LEVEL


def xp_progress(xp: int) -> tuple[int, int]:
    """(xp into current level, xp needed for the level) for a progress bar."""
    return xp % XP_PER_LEVEL, XP_PER_LEVEL


def _promote(division: str) -> str:
    i = DIVISIONS.index(division)
    return DIVISIONS[min(i + 1, len(DIVISIONS) - 1)]


def _relegate(division: str) -> str:
    i = DIVISIONS.index(division)
    return DIVISIONS[max(i - 1, 0)]


@dataclass
class GameweekOutcome:
    number: int
    scored: int


def _portfolio_return(db: Session, portfolio: Portfolio, start: date, end: date) -> float | None:
    """Return over [start, end] using snapshots at those dates (taking them if
    missing). Point-in-time via take_snapshot's as_of."""
    from datetime import datetime, timedelta, timezone

    def equity_on(d: date) -> float:
        as_of = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        take_snapshot(db, portfolio.id, portfolio.base_currency, d, as_of=as_of)
        v = value_portfolio(db, portfolio.id, portfolio.base_currency, as_of=as_of)
        return float(v.equity)

    e0, e1 = equity_on(start), equity_on(end)
    if e0 <= 0:
        return None
    return e1 / e0 - 1.0


def run_gameweek(db: Session, *, number: int, start: date, end: date) -> GameweekOutcome:
    """Score a gameweek: rank each division by return, award XP + points, and
    apply promotion/relegation. Idempotent per (gameweek, user)."""
    gw = db.scalar(select(Gameweek).where(Gameweek.number == number))
    if gw is None:
        from app.services.season import get_or_create_active_season

        season = get_or_create_active_season(db)
        gw = Gameweek(number=number, start_date=start, end_date=end, season_id=season.id)
        db.add(gw)
        db.flush()

    # One portfolio per user (their team). Gather each user's weekly return.
    users = db.scalars(select(User).where(User.password_hash.isnot(None))).all()
    scored: list[tuple[User, Portfolio, float]] = []
    for u in users:
        pf = db.scalar(select(Portfolio).where(Portfolio.user_id == u.id).limit(1))
        if pf is None:
            continue
        r = _portfolio_return(db, pf, start, end)
        if r is None:
            continue
        scored.append((u, pf, r))

    # Rank within each division; award like FC Division Rivals.
    by_div: dict[str, list[tuple[User, Portfolio, float]]] = {}
    for u, pf, r in scored:
        by_div.setdefault(u.division, []).append((u, pf, r))

    for division, rows in by_div.items():
        rows.sort(key=lambda t: t[2], reverse=True)
        n = len(rows)
        for idx, (u, pf, r) in enumerate(rows):
            frac = idx / n if n > 1 else 0.0
            if frac < 0.4:
                pts, tier_xp = 3, 60  # win
            elif frac < 0.8:
                pts, tier_xp = 1, 35  # draw
            else:
                pts, tier_xp = -2, 15  # loss
            perf_xp = max(0, round(r * 400))
            xp = tier_xp + perf_xp

            existing = db.scalar(
                select(GameweekResult).where(
                    GameweekResult.gameweek_id == gw.id, GameweekResult.user_id == u.id
                )
            )
            if existing is not None:
                continue  # already scored this user for this gameweek
            db.add(
                GameweekResult(
                    gameweek_id=gw.id, user_id=u.id, division=division, score=r,
                    rank=idx + 1, xp_awarded=xp, points_awarded=pts,
                )
            )
            u.xp += xp
            u.level = level_for_xp(u.xp)
            u.division_points += pts
            if u.division_points >= PROMOTE_AT and u.division != DIVISIONS[-1]:
                u.division = _promote(u.division)
                u.division_points = 0
            elif u.division_points <= RELEGATE_AT and u.division != DIVISIONS[0]:
                u.division = _relegate(u.division)
                u.division_points = 3

    gw.status = "scored"
    db.commit()
    return GameweekOutcome(number=number, scored=len(scored))


@dataclass
class StandingRow:
    username: str
    display_name: str
    level: int
    xp: int
    division_points: int
    is_me: bool


@dataclass
class WorldRow:
    rank: int
    username: str
    division: str
    level: int
    xp: int
    division_points: int
    is_me: bool


@dataclass
class World:
    total: int
    your_rank: int | None
    your_percentile: float | None  # top X% (lower is better)
    top: list[WorldRow] = field(default_factory=list)


def world_standings(db: Session, me_id: uuid.UUID | None = None, top: int = 15) -> World:
    """Global cross-division ranking of every manager: division tier, then points,
    then XP. The 'against the world' board."""
    users = db.scalars(select(User).where(User.password_hash.isnot(None))).all()
    users.sort(
        key=lambda u: (DIVISIONS.index(u.division), u.division_points, u.xp), reverse=True
    )
    n = len(users)
    your_rank = next((i + 1 for i, u in enumerate(users) if u.id == me_id), None)
    your_pct = round(your_rank / n * 100, 1) if (your_rank and n) else None

    rows = [
        WorldRow(
            rank=i + 1, username=u.username or u.display_name, division=u.division,
            level=u.level, xp=u.xp, division_points=u.division_points, is_me=(u.id == me_id),
        )
        for i, u in enumerate(users[:top])
    ]
    return World(total=n, your_rank=your_rank, your_percentile=your_pct, top=rows)


def division_standings(db: Session, division: str, me_id: uuid.UUID | None = None) -> list[StandingRow]:
    users = db.scalars(
        select(User)
        .where(User.division == division, User.password_hash.isnot(None))
        .order_by(User.division_points.desc(), User.xp.desc())
    ).all()
    return [
        StandingRow(
            username=u.username or u.display_name,
            display_name=u.display_name,
            level=u.level,
            xp=u.xp,
            division_points=u.division_points,
            is_me=(u.id == me_id),
        )
        for u in users
    ]
