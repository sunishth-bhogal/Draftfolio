"""ORM tables — the persistence shell around the pure ledger domain.

Mirrors the four-table decision in DESIGN.md:
  * ``orders``        — what the user requested (immutable)
  * ``transactions``  — what executed (append-only ledger, source of truth)
  * ``positions`` / ``cash_balances`` — derived caches of the folded log
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Money4, Qty8


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Auth
    username: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Progression (NHL-FS style ladder)
    xp: Mapped[int] = mapped_column(default=0)
    level: Mapped[int] = mapped_column(default=1)
    division: Mapped[str] = mapped_column(String(20), default="Bronze")
    division_points: Mapped[int] = mapped_column(default=0)
    # Pack economy (12-hour player packs)
    last_claim_date: Mapped[object | None] = mapped_column(Date, nullable=True)  # legacy cash pack
    last_pack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_streak: Mapped[int] = mapped_column(default=0)


class Season(Base):
    """A Draftfolio season = a real sports season (e.g., 2025-26, Oct–Apr).

    Gameweeks run its full length; at the end, standings are finalized, rewards
    paid, and divisions reset for the next season (net worth/collection persists).
    """

    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(20), unique=True)  # "2025-26"
    start_date: Mapped[object] = mapped_column(Date)
    end_date: Mapped[object] = mapped_column(Date)
    total_gameweeks: Mapped[int] = mapped_column(default=26)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | ended
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Gameweek(Base):
    __tablename__ = "gameweeks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id"), nullable=True, index=True)
    number: Mapped[int] = mapped_column(unique=True)
    start_date: Mapped[object] = mapped_column(Date)
    end_date: Mapped[object] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | scored


class SeasonResult(Base):
    """A user's finishing record for a season — for history and the hall of fame."""

    __tablename__ = "season_results"
    __table_args__ = (
        UniqueConstraint("season_id", "user_id", name="uq_season_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    final_division: Mapped[str] = mapped_column(String(20))
    rank: Mapped[int] = mapped_column(default=0)  # overall rank that season
    division_points: Mapped[int] = mapped_column(default=0)
    xp_at_end: Mapped[int] = mapped_column(default=0)
    reward_xp: Mapped[int] = mapped_column(default=0)
    reward_cash: Mapped[int] = mapped_column(default=0)


class GameweekResult(Base):
    __tablename__ = "gameweek_results"
    __table_args__ = (
        UniqueConstraint("gameweek_id", "user_id", name="uq_gw_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    gameweek_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gameweeks.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    division: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(default=0.0)  # portfolio return that week
    rank: Mapped[int] = mapped_column(default=0)
    xp_awarded: Mapped[int] = mapped_column(default=0)
    points_awarded: Mapped[int] = mapped_column(default=0)


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    asset_class: Mapped[str] = mapped_column(String(20), default="EQUITY")  # EQUITY | ETF | PLAYER
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Player fields (null for stocks/ETFs).
    sport: Mapped[str | None] = mapped_column(String(10), nullable=True)  # NBA | NHL
    team: Mapped[str | None] = mapped_column(String(60), nullable=True)
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ESPN athlete id
    headshot_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # v2 shrinkage prior (player quality): previous-season value for veterans, a
    # position-based league prior for rookies. Separate from current-season data.
    prior_value: Mapped[float | None] = mapped_column(nullable=True)
    prior_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    injury_status: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    base_currency: Mapped[str] = mapped_column(String(3), default="CAD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Order(Base):
    """What the user requested. Immutable once written.

    The ``(portfolio_id, idempotency_key)`` unique constraint is the database-level
    guarantee behind idempotent order processing: a retried request can insert at
    most one row.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "idempotency_key", name="uq_orders_portfolio_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    side: Mapped[str] = mapped_column(String(4))  # BUY / SELL
    instrument_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"))
    quantity: Mapped[object] = mapped_column(Qty8)
    price: Mapped[object] = mapped_column(Money4)
    currency: Mapped[str] = mapped_column(String(3))
    fee: Mapped[object] = mapped_column(Money4)
    status: Mapped[str] = mapped_column(String(12), default="FILLED")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Transaction(Base):
    """Append-only ledger leg. Never updated or deleted."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    account: Mapped[str] = mapped_column(String(60))  # CASH:CAD or POSITION:AAPL
    cash_delta: Mapped[object | None] = mapped_column(Money4, nullable=True)
    cash_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    quantity_delta: Mapped[object | None] = mapped_column(Qty8, nullable=True)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("instruments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Position(Base):
    """Derived cache: current share quantity per instrument."""

    __tablename__ = "positions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), primary_key=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id"), primary_key=True
    )
    quantity: Mapped[object] = mapped_column(Qty8, default=0)

    instrument: Mapped[Instrument] = relationship()


class CashBalance(Base):
    """Derived cache: current cash per currency."""

    __tablename__ = "cash_balances"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), primary_key=True
    )
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    amount: Mapped[object] = mapped_column(Money4, default=0)


class PriceBar(Base):
    """A daily (adjusted) closing price.

    ``as_of`` records *when this datum became available to us*, which is what
    prevents look-ahead bias: valuation only ever reads bars whose ``as_of`` is
    at or before the valuation time, so a backtest can never peek at a price that
    wasn't known yet. ``source`` lets the UI show data provenance.
    """

    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "bar_date", "source", name="uq_price_bar"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id"), index=True
    )
    bar_date: Mapped[object] = mapped_column(Date)
    close: Mapped[object] = mapped_column(Money4)
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(40), default="seed")
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # For computed (player) prices: which valuation formula produced this value.
    formula_version: Mapped[str | None] = mapped_column(String(20), nullable=True)


class PortfolioSnapshot(Base):
    """Historical calculated state — one row per portfolio per day.

    Equity is stored; returns are *derived* from the series on read, so there is
    a single source of truth for each day's value.
    """

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_snapshot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), index=True
    )
    snapshot_date: Mapped[object] = mapped_column(Date)
    cash: Mapped[object] = mapped_column(Money4)
    market_value: Mapped[object] = mapped_column(Money4)
    equity: Mapped[object] = mapped_column(Money4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EtfConstituent(Base):
    """Membership of a player-index ETF: which players it holds, and at what weight.

    An ETF is an Instrument (asset_class='ETF'); its price is the weighted basket
    of its constituents' values, so it gets a real history from the underlying.
    """

    __tablename__ = "etf_constituents"
    __table_args__ = (
        UniqueConstraint("etf_id", "member_id", name="uq_etf_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    etf_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"), index=True)
    weight: Mapped[float] = mapped_column(default=1.0)


class PlayerGame(Base):
    """Raw per-game observation for a player — the immutable source data.

    Kept SEPARATE from computed prices (PriceBar) so valuations are reproducible
    and auditable: re-run any formula version over these rows to regenerate the
    price history. ``as_of`` marks when the box score became available.
    """

    __tablename__ = "player_games"
    __table_args__ = (
        UniqueConstraint("instrument_id", "espn_event_id", name="uq_player_game"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id"), index=True
    )
    espn_event_id: Mapped[str] = mapped_column(String(20))
    game_date: Mapped[object] = mapped_column(Date, index=True)
    opponent: Mapped[str | None] = mapped_column(String(60), nullable=True)
    home: Mapped[bool] = mapped_column(default=True)
    minutes: Mapped[float] = mapped_column(default=0.0)
    points: Mapped[float] = mapped_column(default=0.0)
    rebounds: Mapped[float] = mapped_column(default=0.0)
    assists: Mapped[float] = mapped_column(default=0.0)
    steals: Mapped[float] = mapped_column(default=0.0)
    blocks: Mapped[float] = mapped_column(default=0.0)
    turnovers: Mapped[float] = mapped_column(default=0.0)
    # Sport-agnostic: raw stats as JSON + the computed per-game production score,
    # so hockey (and future sports) reuse the same value/breakdown pipeline.
    stats_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    production: Mapped[float | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="nba_espn")
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SignalEvent(Base):
    """A read-only, non-price signal (news, prediction-market odds, social).

    Deliberately NOT on the ledger write path — signals only ever annotate
    movements after the fact. All sources flatten into this one shape so the
    explainer doesn't care where a signal came from. ``instrument_id`` is null
    for market-wide signals. ``value``/``confidence`` are float estimates.
    """

    __tablename__ = "signal_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(40))  # news | prediction_market | social
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("instruments.id"), nullable=True, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(40))  # sentiment | event_probability | ...
    value: Mapped[float] = mapped_column()
    confidence: Mapped[float] = mapped_column()
    headline: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
