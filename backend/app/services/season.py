"""Seasons — a Draftfolio season runs a full real sports season, then finalizes.

At season end: rank everyone, record their finish, pay rewards (XP + cash scaled
by final division), and reset the ladder to Bronze for the next season. Net worth
and collections persist — only the competition resets, so every season is a fresh
race but your team is still yours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Gameweek, Portfolio, Season, SeasonResult, User
from app.services import bootstrap
from app.services.rivals import DIVISIONS

# Default season window (real 2025-26 regular season) and reward scale by division.
DEFAULT_SEASON = ("2025-26", date(2025, 10, 21), date(2026, 4, 15), 26)
DIVISION_REWARD = {
    "Bronze": (150, 500),
    "Silver": (300, 1500),
    "Gold": (600, 4000),
    "Platinum": (1000, 8000),
    "Diamond": (2000, 20000),
}  # (reward_xp, reward_cash)


def get_or_create_active_season(db: Session) -> Season:
    s = db.scalar(select(Season).where(Season.status == "active"))
    if s is None:
        name, start, end, total = DEFAULT_SEASON
        s = db.scalar(select(Season).where(Season.name == name))
        if s is None:
            s = Season(name=name, start_date=start, end_date=end, total_gameweeks=total, status="active")
            db.add(s)
            db.commit()
    return s


@dataclass
class SeasonState:
    name: str
    start_date: date
    end_date: date
    total_gameweeks: int
    current_gameweek: int  # scored gameweeks so far
    status: str
    your_division: str | None = None
    your_points: int | None = None
    your_rank: int | None = None  # rank within your division


def season_state(db: Session, user: User | None = None) -> SeasonState:
    s = get_or_create_active_season(db)
    scored = db.scalar(
        select(func.count()).select_from(Gameweek).where(
            Gameweek.season_id == s.id, Gameweek.status == "scored"
        )
    ) or 0

    st = SeasonState(
        name=s.name, start_date=s.start_date, end_date=s.end_date,
        total_gameweeks=s.total_gameweeks, current_gameweek=int(scored), status=s.status,
    )
    if user is not None:
        peers = db.scalars(
            select(User).where(User.division == user.division, User.password_hash.isnot(None))
            .order_by(User.division_points.desc(), User.xp.desc())
        ).all()
        st.your_division = user.division
        st.your_points = user.division_points
        st.your_rank = next((i + 1 for i, u in enumerate(peers) if u.id == user.id), None)
    return st


@dataclass
class SeasonFinale:
    season: str
    finalized: int


def end_season(db: Session) -> SeasonFinale:
    """Finalize the active season: record results, pay rewards, reset the ladder,
    and open the next season."""
    s = get_or_create_active_season(db)

    users = db.scalars(select(User).where(User.password_hash.isnot(None))).all()
    # Overall rank: higher division first, then division points, then xp.
    users.sort(
        key=lambda u: (DIVISIONS.index(u.division), u.division_points, u.xp), reverse=True
    )

    for rank, u in enumerate(users, start=1):
        rxp, rcash = DIVISION_REWARD.get(u.division, (150, 500))
        db.add(
            SeasonResult(
                season_id=s.id, user_id=u.id, final_division=u.division, rank=rank,
                division_points=u.division_points, xp_at_end=u.xp,
                reward_xp=rxp, reward_cash=rcash,
            )
        )
        # Pay rewards: XP persists progression; cash goes to the team.
        u.xp += rxp
        from app.services.rivals import level_for_xp

        u.level = level_for_xp(u.xp)
        pf = db.scalar(select(Portfolio).where(Portfolio.user_id == u.id).limit(1))
        if pf is not None:
            bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal(rcash), currency=pf.base_currency)
        # Reset the ladder for next season (collection/net worth untouched).
        u.division = "Bronze"
        u.division_points = 0

    s.status = "ended"
    db.commit()

    # Open the next season.
    _open_next_season(db, s)
    return SeasonFinale(season=s.name, finalized=len(users))


def _open_next_season(db: Session, ended: Season) -> Season:
    try:
        start_year = int(ended.name.split("-")[0]) + 1
        name = f"{start_year}-{str(start_year + 1)[-2:]}"
    except ValueError:
        name = ended.name + "-next"
    from datetime import timedelta

    nxt = Season(
        name=name,
        start_date=ended.start_date.replace(year=ended.start_date.year + 1),
        end_date=ended.end_date.replace(year=ended.end_date.year + 1),
        total_gameweeks=ended.total_gameweeks,
        status="active",
    )
    db.add(nxt)
    db.commit()
    return nxt
