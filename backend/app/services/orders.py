"""Order service — orchestrates the pure domain over the database.

Flow for ``place_order``:
  1. Idempotency pre-check: if an order with this ``(portfolio, key)`` already
     exists, return it unchanged (a safe replay).
  2. Load the derived cash/positions into an in-memory domain ``Account``.
  3. Call the pure ``Account.apply_order`` — this is where money invariants and
     insufficient-funds/shares checks live.
  4. Persist: insert the immutable order, append transaction legs, update the
     derived caches — all in one DB transaction.

The unique constraint on ``(portfolio_id, idempotency_key)`` is the real
guarantee: if two identical requests race past the pre-check, the second insert
raises ``IntegrityError`` and we fall back to returning the winner.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import ledger
from app.domain.money import Money
from app.models import CashBalance, Instrument, Order, Portfolio, Position, Transaction


class PortfolioNotFound(LookupError):
    pass


class InstrumentNotFound(LookupError):
    pass


@dataclass
class OrderResult:
    order: Order
    created: bool  # False => idempotent replay of an existing order


def _load_account(db: Session, portfolio: Portfolio) -> tuple[ledger.Account, dict[str, uuid.UUID]]:
    """Rehydrate a domain Account from the derived caches, keyed by symbol."""
    account = ledger.Account(base_currency=portfolio.base_currency)

    for cb in db.scalars(
        select(CashBalance).where(CashBalance.portfolio_id == portfolio.id)
    ):
        account.cash[cb.currency] = Money(cb.amount, cb.currency)

    symbol_to_id: dict[str, uuid.UUID] = {}
    for pos, inst in db.execute(
        select(Position, Instrument)
        .join(Instrument, Position.instrument_id == Instrument.id)
        .where(Position.portfolio_id == portfolio.id)
    ):
        account.positions[inst.symbol] = pos.quantity
        symbol_to_id[inst.symbol] = inst.id

    return account, symbol_to_id


def _apply_leg_to_cache(
    db: Session,
    portfolio_id: uuid.UUID,
    leg: ledger.TransactionLeg,
    symbol_to_id: dict[str, uuid.UUID],
) -> None:
    if leg.cash_delta is not None:
        ccy = leg.cash_delta.currency
        cb = db.get(CashBalance, {"portfolio_id": portfolio_id, "currency": ccy})
        if cb is None:
            cb = CashBalance(portfolio_id=portfolio_id, currency=ccy, amount=Decimal("0"))
            db.add(cb)
        cb.amount = Decimal(cb.amount) + leg.cash_delta.amount
    if leg.quantity_delta is not None:
        symbol = leg.account.split("POSITION:", 1)[1]
        instrument_id = symbol_to_id[symbol]
        pos = db.get(
            Position, {"portfolio_id": portfolio_id, "instrument_id": instrument_id}
        )
        if pos is None:
            pos = Position(
                portfolio_id=portfolio_id, instrument_id=instrument_id, quantity=Decimal("0")
            )
            db.add(pos)
        pos.quantity = Decimal(pos.quantity) + leg.quantity_delta


def place_order(
    db: Session,
    *,
    portfolio_id: uuid.UUID,
    idempotency_key: str,
    side: str,
    symbol: str,
    quantity: Decimal,
    price: Decimal,
    currency: str,
    fee: Decimal = Decimal("0"),
) -> OrderResult:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise PortfolioNotFound(str(portfolio_id))

    # (1) idempotency pre-check
    existing = db.scalar(
        select(Order).where(
            Order.portfolio_id == portfolio_id,
            Order.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return OrderResult(order=existing, created=False)

    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if instrument is None:
        raise InstrumentNotFound(symbol)

    # (2)+(3) apply against the pure domain — raises on invariant violation
    account, symbol_to_id = _load_account(db, portfolio)
    symbol_to_id[symbol] = instrument.id
    domain_order = ledger.Order(
        order_id=str(uuid.uuid4()),
        side=ledger.Side(side),
        instrument=symbol,
        quantity=quantity,
        price=Money(price, currency),
        fee=Money(fee, currency),
    )
    legs = account.apply_order(domain_order)  # InsufficientCash / InsufficientShares

    # (4) persist
    order = Order(
        portfolio_id=portfolio_id,
        idempotency_key=idempotency_key,
        side=side,
        instrument_id=instrument.id,
        quantity=quantity,
        price=price,
        currency=currency,
        fee=fee,
        status="FILLED",
    )
    db.add(order)
    try:
        db.flush()  # surfaces the unique-constraint race here
    except IntegrityError:
        db.rollback()
        winner = db.scalar(
            select(Order).where(
                Order.portfolio_id == portfolio_id,
                Order.idempotency_key == idempotency_key,
            )
        )
        return OrderResult(order=winner, created=False)

    for leg in legs:
        instrument_id = (
            instrument.id if leg.account.startswith("POSITION:") else None
        )
        db.add(
            Transaction(
                portfolio_id=portfolio_id,
                order_id=order.id,
                account=leg.account,
                cash_delta=(leg.cash_delta.amount if leg.cash_delta else None),
                cash_currency=(leg.cash_delta.currency if leg.cash_delta else None),
                quantity_delta=leg.quantity_delta,
                instrument_id=instrument_id,
            )
        )
        _apply_leg_to_cache(db, portfolio_id, leg, symbol_to_id)

    db.commit()
    return OrderResult(order=order, created=True)
