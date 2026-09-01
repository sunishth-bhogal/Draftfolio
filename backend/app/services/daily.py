"""Player-pack economy.

Every 12 hours you open a pack and pull a random player (weighted by rarity),
granted as ~$1,000 of shares in your team. You own the card outright — its value
then floats with that player, and you can hold or sell it. This is the collectible
loop that brings people back twice a day.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Instrument, Portfolio, User
from app.services import bootstrap
from app.services.rivals import level_for_xp

PACK_VALUE = 1000
COOLDOWN = timedelta(hours=12)
XP_PER_PACK = 30
MIN_PLAYER_PRICE = 80

# (tier, weight, min_price, max_price) — commons common, legends rare.
TIERS = [
    ("common", 70, 80, 350),
    ("rare", 22, 350, 500),
    ("epic", 7, 500, 650),
    ("legendary", 1, 650, 1_000_000),
]


class OnCooldown(RuntimeError):
    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"pack on cooldown for {seconds}s")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _candidates(db: Session):
    rows = db.execute(
        text(
            """
            SELECT i.id, i.symbol, i.name, i.sport, i.headshot_url,
                   (SELECT pb.close FROM price_bars pb
                    WHERE pb.instrument_id = i.id ORDER BY pb.bar_date DESC LIMIT 1) AS price
            FROM instruments i WHERE i.asset_class = 'PLAYER'
            """
        )
    ).fetchall()
    return [r for r in rows if r.price is not None and float(r.price) >= MIN_PLAYER_PRICE]


def _pick(db: Session):
    cands = _candidates(db)
    if not cands:
        return None, "common"
    weights = [t[1] for t in TIERS]
    for _ in range(6):
        tier = random.choices(TIERS, weights=weights)[0]
        pool = [c for c in cands if tier[2] <= float(c.price) < tier[3]]
        if pool:
            return random.choice(pool), tier[0]
    return random.choice(cands), "common"


@dataclass
class PackResult:
    instrument_id: str
    player: str
    sport: str | None
    headshot_url: str | None
    tier: str
    shares: int
    value: float
    xp_awarded: int
    streak: int


@dataclass
class PackStatus:
    can_claim: bool
    seconds_remaining: int
    streak: int
    cooldown_hours: int


def _portfolio(db: Session, user: User) -> Portfolio | None:
    return db.scalar(select(Portfolio).where(Portfolio.user_id == user.id).limit(1))


def status(db: Session, user: User, now: datetime | None = None) -> PackStatus:
    now = now or datetime.now(timezone.utc)
    last = _aware(user.last_pack_at)
    if last is None:
        return PackStatus(True, 0, user.login_streak, int(COOLDOWN.total_seconds() // 3600))
    remaining = max(0, int((COOLDOWN - (now - last)).total_seconds()))
    return PackStatus(remaining == 0, remaining, user.login_streak, int(COOLDOWN.total_seconds() // 3600))


def claim(db: Session, user: User, now: datetime | None = None) -> PackResult:
    now = now or datetime.now(timezone.utc)
    last = _aware(user.last_pack_at)
    if last is not None:
        elapsed = now - last
        if elapsed < COOLDOWN:
            raise OnCooldown(int((COOLDOWN - elapsed).total_seconds()))

    cand, tier = _pick(db)
    if cand is None:
        raise RuntimeError("no players available")
    price = float(cand.price)
    # One share per card: a pull is worth exactly that player — pulling a star is
    # a jackpot, and you can't launder cheap cards into an expensive one.
    shares = 1

    pf = _portfolio(db, user)
    if pf is None:
        raise RuntimeError("user has no team")
    inst = db.get(Instrument, uuid.UUID(str(cand.id)))
    bootstrap.grant_shares(db, portfolio_id=pf.id, instrument=inst, quantity=Decimal(shares))

    # Streak: consecutive-ish engagement (claim within 40h keeps it alive).
    streak = user.login_streak + 1 if (last is not None and (now - last) < timedelta(hours=40)) else 1
    user.login_streak = streak
    user.last_pack_at = now
    user.xp += XP_PER_PACK
    user.level = level_for_xp(user.xp)
    db.commit()

    return PackResult(
        instrument_id=str(inst.id),
        player=cand.name,
        sport=cand.sport,
        headshot_url=cand.headshot_url,
        tier=tier,
        shares=shares,
        value=round(shares * price, 2),
        xp_awarded=XP_PER_PACK,
        streak=streak,
    )
