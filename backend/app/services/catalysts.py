"""Daily price catalysts — the *why* behind a player's latest value move.

Deterministic, derived from stored raw games (+ injury status). Sport-agnostic:
performance direction uses the stored per-game production; the box line is
formatted per sport. Both power the player page's "What moved it" and are emitted
as signal_events for the portfolio "why did it move?" explainer.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.player_value import form_multiplier
from app.models import Instrument, PlayerGame, PriceBar, SignalEvent

FORM_WINDOW = 5


@dataclass
class Catalyst:
    kind: str  # performance | minutes | form | availability | schedule
    direction: str  # up | down | neutral
    label: str
    detail: str


@dataclass
class Catalysts:
    available: bool
    as_of: object | None = None
    price_change: float | None = None
    summary: str = ""
    items: list[Catalyst] = field(default_factory=list)


def _prod(g: PlayerGame, sport: str = "NBA") -> float:
    from app.services.game_stats import game_production

    return game_production(g, sport)


def _box_line(g: PlayerGame, sport: str) -> str:
    from app.services.game_stats import game_stats

    stats = game_stats(g)
    if sport == "NHL":
        return f"{stats.get('goals', 0):.0f} G, {stats.get('assists', 0):.0f} A, {stats.get('shots', 0):.0f} SOG"
    return f"{stats.get('points', 0):.0f} PTS, {stats.get('rebounds', 0):.0f} REB, {stats.get('assists', 0):.0f} AST"


def _close_on(db: Session, instrument_id: uuid.UUID, bar_date) -> float | None:
    bar = db.scalar(
        select(PriceBar).where(
            PriceBar.instrument_id == instrument_id,
            PriceBar.bar_date == bar_date,
            PriceBar.source == "espn",
        )
    )
    return float(bar.close) if bar is not None else None


def _game_over_game_change(db, instrument_id, games: list[PlayerGame]) -> float | None:
    if len(games) < 2:
        return None
    a = _close_on(db, instrument_id, games[-2].game_date)
    b = _close_on(db, instrument_id, games[-1].game_date)
    if a is None or b is None or a == 0:
        return None
    return b / a - 1.0


def player_catalysts(db: Session, instrument_id: uuid.UUID) -> Catalysts:
    inst = db.get(Instrument, instrument_id)
    games = list(
        db.scalars(
            select(PlayerGame)
            .where(PlayerGame.instrument_id == instrument_id)
            .order_by(PlayerGame.game_date.asc())
        )
    )
    if not inst or not games:
        return Catalysts(available=False)

    sport = inst.sport or "NBA"
    last = games[-1]
    season_prod = sum(_prod(g, sport) for g in games) / len(games)
    last_prod = _prod(last, sport)
    items: list[Catalyst] = []

    box = _box_line(last, sport)
    if last_prod >= season_prod * 1.15:
        items.append(Catalyst("performance", "up", "Big game", f"{box} — above the season norm"))
    elif last_prod <= season_prod * 0.85:
        items.append(Catalyst("performance", "down", "Quiet game", f"{box} — below the season norm"))
    else:
        items.append(Catalyst("performance", "neutral", "In line", f"{box} — around the norm"))

    prior_games = games[:-1]
    if prior_games:
        recent10 = prior_games[-10:]
        avg_min = sum(g.minutes for g in recent10) / len(recent10)
        unit = "min"
        if last.minutes >= avg_min + 4:
            items.append(Catalyst("minutes", "up", "Elevated ice time", f"{last.minutes:.0f} {unit} vs ~{avg_min:.0f} usual"))
        elif last.minutes <= avg_min - 6:
            items.append(Catalyst("minutes", "down", "Reduced ice time", f"{last.minutes:.0f} {unit} vs ~{avg_min:.0f} usual"))

    recent = [_prod(g, sport) for g in games[-FORM_WINDOW:]]
    form = form_multiplier(sum(recent) / len(recent), season_prod)
    if form >= 1.05:
        items.append(Catalyst("form", "up", "Hot streak", f"last {min(FORM_WINDOW, len(games))} games running +{(form - 1) * 100:.0f}%"))
    elif form <= 0.95:
        items.append(Catalyst("form", "down", "Cold streak", f"last {min(FORM_WINDOW, len(games))} games {(form - 1) * 100:.0f}%"))

    if inst.injury_status:
        items.append(Catalyst("availability", "down", f"Listed {inst.injury_status}", "availability discount applied"))

    if last.opponent:
        items.append(Catalyst("schedule", "neutral", f"vs {last.opponent}", "most recent matchup"))

    drivers = [c for c in items if c.direction != "neutral"]
    summary = "; ".join(f"{c.label.lower()} ({c.detail})" for c in drivers[:2]) or "no notable catalysts"

    return Catalysts(
        available=True,
        as_of=last.game_date,
        price_change=_game_over_game_change(db, instrument_id, games),
        summary=summary,
        items=items,
    )


def write_catalyst_signal(db: Session, instrument: Instrument) -> SignalEvent | None:
    cats = player_catalysts(db, instrument.id)
    if not cats.available:
        return None
    notable = next(
        (c for c in cats.items if c.kind in {"performance", "availability"} and c.direction != "neutral"),
        None,
    )
    if notable is None:
        return None
    ts = datetime.combine(cats.as_of, datetime.min.time(), tzinfo=timezone.utc)
    sig = SignalEvent(
        instrument_id=instrument.id,
        ts=ts,
        source="catalyst",
        signal_type=notable.kind,
        value=1.0 if notable.direction == "up" else -1.0,
        confidence=0.6,
        headline=f"{instrument.name}: {notable.label} — {notable.detail}",
        source_url=None,
    )
    db.add(sig)
    return sig
