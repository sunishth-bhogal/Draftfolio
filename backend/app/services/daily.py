"""Daily pack economy.

Players start with $0 and build capital by logging in: each day you claim a pack
worth $100–$1,000 (bigger with a longer streak), credited to your team's cash
through the ledger. A first-ever claim is a larger welcome pack so day one isn't
dead. This is the habit loop that grows the app before global rank matters.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Portfolio, User
from app.services import bootstrap
from app.services.rivals import level_for_xp

WELCOME_PACK = 1000
MIN_REWARD = 100
MAX_REWARD = 1000


class AlreadyClaimed(RuntimeError):
    pass


def reward_for_streak(streak: int) -> int:
    """$100 at streak 1, ramping to the $1,000 cap by ~day 8, with some jitter
    for a pack-opening feel. Always in [100, 1000], rounded to $10."""
    base = min(MAX_REWARD, MIN_REWARD + (streak - 1) * 130)
    jitter = random.randint(-40, 120)
    value = max(MIN_REWARD, min(MAX_REWARD, base + jitter))
    return int(round(value / 10) * 10)


@dataclass
class ClaimResult:
    reward: int
    streak: int
    is_welcome: bool
    xp_awarded: int
    new_cash: float


@dataclass
class DailyStatus:
    can_claim: bool
    streak: int
    next_reward_estimate: int


def _portfolio(db: Session, user: User) -> Portfolio | None:
    return db.scalar(select(Portfolio).where(Portfolio.user_id == user.id).limit(1))


def status(db: Session, user: User, today: date | None = None) -> DailyStatus:
    today = today or date.today()
    can = user.last_claim_date != today
    # If the streak would continue tomorrow-from-last it grows; otherwise resets to 1.
    next_streak = user.login_streak + 1 if user.last_claim_date == today - timedelta(days=1) else 1
    est = WELCOME_PACK if user.last_claim_date is None else reward_for_streak(next_streak)
    return DailyStatus(can_claim=can, streak=user.login_streak, next_reward_estimate=est)


def claim(db: Session, user: User, today: date | None = None) -> ClaimResult:
    today = today or date.today()
    if user.last_claim_date == today:
        raise AlreadyClaimed("already claimed today")

    is_welcome = user.last_claim_date is None
    if user.last_claim_date == today - timedelta(days=1):
        streak = user.login_streak + 1  # consecutive day
    else:
        streak = 1  # first claim or a missed day resets the streak

    reward = WELCOME_PACK if is_welcome else reward_for_streak(streak)

    pf = _portfolio(db, user)
    if pf is None:
        raise RuntimeError("user has no team")
    bootstrap.fund_portfolio(
        db, portfolio_id=pf.id, amount=Decimal(str(reward)), currency=pf.base_currency
    )

    xp = 25 + min(streak, 10) * 5
    user.xp += xp
    user.level = level_for_xp(user.xp)
    user.last_claim_date = today
    user.login_streak = streak
    db.commit()

    from app.services.valuation import value_portfolio

    val = value_portfolio(db, pf.id, pf.base_currency)
    return ClaimResult(
        reward=reward, streak=streak, is_welcome=is_welcome, xp_awarded=xp, new_cash=float(val.cash)
    )
