"""Pure, in-memory ledger domain — no database, no framework.

This is the money-correctness core, kept free of infrastructure so it can be
exercised exhaustively with property-based tests. The persistence layer
(SQLAlchemy) and the API layer (FastAPI) are thin shells that call into this.

Design decisions:

* **Double-entry.** Every order produces balanced *legs*: cash moves one way,
  the position moves the other. The legs of a trade always net to zero *value*
  in the trade currency (ignoring fees, which leave the account as a cost). This
  is what makes "money cannot be created" checkable rather than hopeful.
* **Append-only.** ``apply_order`` never edits a past transaction. Positions and
  cash are *derived* by folding the transaction log, so state can always be
  rebuilt and reconciled against what is stored.
* **Idempotent.** Re-applying an order with an id already seen is a no-op that
  returns the original result, so a client retry can never double-spend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List

from .money import Money


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class InsufficientCash(ValueError):
    """The account cannot afford a buy (virtual cash cannot go negative)."""


class InsufficientShares(ValueError):
    """The account cannot sell more shares than it holds (no shorting in v1)."""


@dataclass(frozen=True)
class Order:
    """What the user *requested*. Immutable once created."""

    order_id: str
    side: Side
    instrument: str
    quantity: Decimal
    price: Money
    fee: Money

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.price.is_negative:
            raise ValueError("price cannot be negative")
        if self.fee.is_negative:
            raise ValueError("fee cannot be negative")
        if self.price.currency != self.fee.currency:
            raise ValueError("price and fee must share a currency")

    @property
    def currency(self) -> str:
        return self.price.currency

    @property
    def gross(self) -> Money:
        """Trade value before fees: quantity * price."""
        return self.price * self.quantity


@dataclass(frozen=True)
class TransactionLeg:
    """One side of the double-entry record for an executed order."""

    order_id: str
    account: str  # "CASH:<ccy>" or "POSITION:<instrument>"
    cash_delta: Money | None = None
    quantity_delta: Decimal | None = None


@dataclass
class Account:
    """Derived state: cash per currency and share quantity per instrument.

    ``cash`` and ``positions`` are a *cache* of the folded transaction log, not
    an independent source of truth. :func:`replay` rebuilds them from scratch,
    and the reconciliation check asserts the two agree.
    """

    base_currency: str = "CAD"
    cash: Dict[str, Money] = field(default_factory=dict)
    positions: Dict[str, Decimal] = field(default_factory=dict)
    transactions: List[TransactionLeg] = field(default_factory=list)
    _processed_orders: set[str] = field(default_factory=set)

    def fund(self, amount: Money) -> None:
        """Seed starting virtual cash (the $100k grant)."""
        self.cash[amount.currency] = self.cash_balance(amount.currency) + amount
        self.transactions.append(
            TransactionLeg(order_id="FUND", account=f"CASH:{amount.currency}", cash_delta=amount)
        )

    def cash_balance(self, currency: str) -> Money:
        return self.cash.get(currency, Money.zero(currency))

    def position(self, instrument: str) -> Decimal:
        return self.positions.get(instrument, Decimal("0"))

    def apply_order(self, order: Order) -> List[TransactionLeg]:
        """Execute an order, returning its transaction legs.

        Idempotent: applying an order whose id was already processed returns its
        existing legs and changes nothing.
        """
        if order.order_id in self._processed_orders:
            return [t for t in self.transactions if t.order_id == order.order_id]

        ccy = order.currency
        if order.side is Side.BUY:
            cost = order.gross + order.fee
            if cost > self.cash_balance(ccy):
                raise InsufficientCash(
                    f"need {cost} but have {self.cash_balance(ccy)}"
                )
            cash_delta = -cost
            qty_delta = order.quantity
        else:  # SELL
            if order.quantity > self.position(order.instrument):
                raise InsufficientShares(
                    f"selling {order.quantity} but hold {self.position(order.instrument)}"
                )
            cash_delta = order.gross - order.fee
            qty_delta = -order.quantity

        legs = [
            TransactionLeg(order.order_id, f"CASH:{ccy}", cash_delta=cash_delta),
            TransactionLeg(order.order_id, f"POSITION:{order.instrument}", quantity_delta=qty_delta),
        ]

        # Commit: mutate derived state and append to the log (never edit).
        self.cash[ccy] = self.cash_balance(ccy) + cash_delta
        self.positions[order.instrument] = self.position(order.instrument) + qty_delta
        self.transactions.extend(legs)
        self._processed_orders.add(order.order_id)
        return legs

    def equity(self, marks: Dict[str, Money]) -> Money:
        """Total value = cash + market value of positions, in base currency.

        ``marks`` maps instrument -> current price. For v1 we assume marks are in
        the base currency; FX conversion is a Phase-3 extension.
        """
        total = self.cash_balance(self.base_currency)
        for instrument, qty in self.positions.items():
            if qty == 0:
                continue
            total = total + marks[instrument] * qty
        return total


def replay(legs: List[TransactionLeg], base_currency: str = "CAD") -> Account:
    """Rebuild an Account purely from its transaction log.

    Used by the reconciliation check: independently folding the append-only log
    must reproduce the live derived state, or something has corrupted it.
    """
    acc = Account(base_currency=base_currency)
    for leg in legs:
        if leg.cash_delta is not None:
            ccy = leg.cash_delta.currency
            acc.cash[ccy] = acc.cash_balance(ccy) + leg.cash_delta
        if leg.quantity_delta is not None:
            instrument = leg.account.split("POSITION:", 1)[1]
            acc.positions[instrument] = acc.position(instrument) + leg.quantity_delta
    return acc
