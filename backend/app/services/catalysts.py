"""Daily price catalysts — the *why* behind a player's latest value move.

Deterministic, derived from stored raw games (+ injury status). Each catalyst is
a labeled, directional reason: recent performance vs the player's norm, a minutes
change, hot/cold form, availability, and the opponent faced. These both power the
player page's "What moved it" and are emitted as signal_events so the portfolio
"why did it move?" explainer can surface player-level drivers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.player_value import (
    form_multiplier,
    production_score,
)
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
    price_change: float | None = None  # latest price bar vs the previous one
    summary: str = ""
    items: list[Catalyst] = field(default_factory=list)


def _prod_of(g: PlayerGame) -> float:
    from app.services.player_analysis import _mean_stats

    return production_score(_mean_stats([g]))


def _close_on(db: Session, instrument_id: uuid.UUID, bar_date) -> float | None:
    bar = db.scalar(
        select(PriceBar).where(
            PriceBar.instrument_id == instrument_id,
            PriceBar.bar_date == bar_date,
            PriceBar.source == "nba_espn",
        )
    )
    return float(bar.close) if bar is not None else None


def _game_over_game_change(
    db: Session, instrument_id: uuid.UUID, games: list[PlayerGame]
) -> float | None:
    """Move attributable to the latest game: value on its date vs the prior game's.

    Uses game dates (not the current 'today' mark) so the % move lines up with the
    catalysts that explain it.
    """
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

    last = games[-1]
    season_prod = sum(_prod_of(g) for g in games) / len(games)
    last_prod = _prod_of(last)
    items: list[Catalyst] = []

    # 1) Recent performance vs the player's own norm.
    box = f"{last.points:.0f} PTS, {last.rebounds:.0f} REB, {last.assists:.0f} AST"
    if last_prod >= season_prod * 1.15:
        items.append(Catalyst("performance", "up", "Big game", f"{box} — above the season norm"))
    elif last_prod <= season_prod * 0.85:
        items.append(Catalyst("performance", "down", "Quiet game", f"{box} — below the season norm"))
    else:
        items.append(Catalyst("performance", "neutral", "In line", f"{box} — around the norm"))

    # 2) Minutes vs the trailing average (role change).
    prior_games = games[:-1]
    if prior_games:
        avg_min = sum(g.minutes for g in prior_games[-10:]) / len(prior_games[-10:])
        if last.minutes >= avg_min + 4:
            items.append(Catalyst("minutes", "up", "Elevated minutes", f"{last.minutes:.0f} min vs ~{avg_min:.0f} usual"))
        elif last.minutes <= avg_min - 6:
            items.append(Catalyst("minutes", "down", "Reduced minutes", f"{last.minutes:.0f} min vs ~{avg_min:.0f} usual"))

    # 3) Hot/cold form (last 5 vs season).
    from app.services.player_analysis import _mean_stats

    form = form_multiplier(
        production_score(_mean_stats(games[-FORM_WINDOW:])),
        production_score(_mean_stats(games)),
    )
    if form >= 1.05:
        items.append(Catalyst("form", "up", "Hot streak", f"last {min(FORM_WINDOW, len(games))} games running +{(form - 1) * 100:.0f}%"))
    elif form <= 0.95:
        items.append(Catalyst("form", "down", "Cold streak", f"last {min(FORM_WINDOW, len(games))} games {(form - 1) * 100:.0f}%"))

    # 4) Availability (persisted injury status).
    if inst.injury_status:
        items.append(
            Catalyst("availability", "down", f"Listed {inst.injury_status}", "availability discount applied")
        )

    # 5) Opponent context (not a value driver, but explains the game).
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
    """Emit a signal_event for a notable latest-game catalyst, so the portfolio
    explainer can attribute a move to a player. No-op if nothing notable."""
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
