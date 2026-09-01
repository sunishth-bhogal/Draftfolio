"""Pack store — buy packs with cash. Tiers trade price for odds and card count.

The gamble: you spend cash hoping the cards you pull are worth more than the pack
cost. A legendary pull can pay off many times over; a bad open loses value. Every
card is 1 share (like the free pack), so a card is a card.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import CashBalance, Instrument, Portfolio, Transaction, User

# Rarity by current price.
BANDS = {"common": (80, 350), "rare": (350, 500), "epic": (500, 650), "legendary": (650, 1_000_000)}
RARITY_ORDER = ["common", "rare", "epic", "legendary"]


@dataclass
class Tier:
    key: str
    name: str
    cost: int
    cards: int
    weights: dict[str, int]  # rarity -> weight
    guarantee: str | None  # min rarity guaranteed on at least one card
    blurb: str


# Costs are priced near the expected card value (a card ≈ the player's price) with
# a small house edge, so an open is usually a modest loss but a legendary pull pays
# off — a real gamble, and a cash sink rather than a money printer.
TIERS: list[Tier] = [
    Tier("bronze", "Bronze Pack", 250, 1, {"common": 78, "rare": 18, "epic": 3, "legendary": 1}, None,
         "1 card · mostly role players, small shot at a star"),
    Tier("silver", "Silver Pack", 1000, 3, {"common": 50, "rare": 35, "epic": 12, "legendary": 3}, "rare",
         "3 cards · guaranteed rare+, real shot at an epic"),
    Tier("gold", "Gold Pack", 1500, 3, {"common": 18, "rare": 40, "epic": 30, "legendary": 12}, "epic",
         "3 cards · guaranteed epic+, strong star odds"),
    Tier("elite", "Elite Pack", 3000, 5, {"common": 5, "rare": 28, "epic": 45, "legendary": 22}, "epic",
         "5 cards · loaded odds, best chance at a legendary"),
]
TIER_BY_KEY = {t.key: t for t in TIERS}


class NotEnoughCash(RuntimeError):
    pass


@dataclass
class PulledCard:
    instrument_id: str
    player: str
    sport: str | None
    headshot_url: str | None
    tier: str
    value: float


@dataclass
class OpenResult:
    tier: str
    cost: int
    cards: list[PulledCard]
    total_value: float
    cash: float


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
    return [r for r in rows if r.price is not None and float(r.price) >= BANDS["common"][0]]


def _rarity(price: float) -> str:
    for name, (lo, hi) in BANDS.items():
        if lo <= price < hi:
            return name
    return "common"


def _pick(cands, weights: dict[str, int], min_rarity: str | None = None):
    allowed = RARITY_ORDER[RARITY_ORDER.index(min_rarity):] if min_rarity else RARITY_ORDER
    tiers = [(r, weights.get(r, 0)) for r in allowed if weights.get(r, 0) > 0]
    if not tiers:
        tiers = [(r, 1) for r in allowed]
    for _ in range(8):
        r = random.choices([t[0] for t in tiers], weights=[t[1] for t in tiers])[0]
        lo, hi = BANDS[r]
        pool = [c for c in cands if lo <= float(c.price) < hi]
        if pool:
            return random.choice(pool), r
    return random.choice(cands), "common"


def cash_of(db: Session, pf: Portfolio) -> float:
    cb = db.get(CashBalance, {"portfolio_id": pf.id, "currency": pf.base_currency})
    return float(cb.amount) if cb else 0.0


def _spend(db: Session, pf: Portfolio, amount: int) -> None:
    cb = db.get(CashBalance, {"portfolio_id": pf.id, "currency": pf.base_currency})
    cb.amount = Decimal(cb.amount) - Decimal(amount)
    db.add(
        Transaction(
            portfolio_id=pf.id, order_id=None, account=f"CASH:{pf.base_currency}",
            cash_delta=Decimal(-amount), cash_currency=pf.base_currency,
        )
    )


def _grant(db: Session, pf: Portfolio, inst: Instrument) -> None:
    from app.services.bootstrap import grant_shares

    grant_shares(db, portfolio_id=pf.id, instrument=inst, quantity=Decimal(1))


def open_pack(db: Session, user: User, tier_key: str) -> OpenResult:
    tier = TIER_BY_KEY[tier_key]
    pf = db.scalar(select(Portfolio).where(Portfolio.user_id == user.id).limit(1))
    if pf is None:
        raise RuntimeError("no team")
    if cash_of(db, pf) < tier.cost:
        raise NotEnoughCash(f"need ${tier.cost}")

    cands = _candidates(db)
    if not cands:
        raise RuntimeError("no players available")

    _spend(db, pf, tier.cost)

    pulls: list = []
    for _ in range(tier.cards):
        pulls.append(_pick(cands, tier.weights))
    # Enforce the guarantee: at least one card >= guarantee rarity.
    if tier.guarantee:
        gi = RARITY_ORDER.index(tier.guarantee)
        if not any(RARITY_ORDER.index(r) >= gi for _c, r in pulls):
            pulls[0] = _pick(cands, tier.weights, min_rarity=tier.guarantee)

    cards: list[PulledCard] = []
    for cand, r in pulls:
        inst = db.get(Instrument, uuid.UUID(str(cand.id)))
        _grant(db, pf, inst)
        cards.append(
            PulledCard(
                instrument_id=str(inst.id), player=cand.name, sport=cand.sport,
                headshot_url=cand.headshot_url, tier=r, value=round(float(cand.price), 2),
            )
        )
    db.commit()

    return OpenResult(
        tier=tier_key, cost=tier.cost, cards=cards,
        total_value=round(sum(c.value for c in cards), 2), cash=cash_of(db, pf),
    )
