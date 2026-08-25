"""Property-based tests for the ledger's financial invariants.

Instead of a handful of hand-picked examples, Hypothesis generates thousands of
random-but-valid trade sequences and asserts the invariants hold for all of
them. These are the statements that make the project credible for a fintech
role: *money is conserved*, *state is reconstructable*, *retries are safe*.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.ledger import (
    Account,
    InsufficientCash,
    Order,
    Side,
    replay,
)
from app.domain.money import Money

CCY = "CAD"


def cad(x) -> Money:
    return Money(Decimal(str(x)), CCY)


# --- strategies ---------------------------------------------------------------

prices = st.decimals(min_value=Decimal("1.00"), max_value=Decimal("500.00"), places=2)
quantities = st.decimals(min_value=Decimal("1"), max_value=Decimal("100"), places=0)
fees = st.decimals(min_value=Decimal("0.00"), max_value=Decimal("5.00"), places=2)


def funded_account(starting=Decimal("100000")) -> Account:
    acc = Account(base_currency=CCY)
    acc.fund(cad(starting))
    return acc


# --- invariants ---------------------------------------------------------------


@given(price=prices, qty=quantities, fee=fees)
@settings(max_examples=300)
def test_buy_then_sell_at_same_price_costs_only_fees(price, qty, fee):
    """Round-tripping a position at an unchanged mark can only lose fees.

    Equity afterwards must equal starting equity minus the two fees — never
    more (money created) and never a surprise extra loss.
    """
    acc = funded_account()
    p = Money(price, CCY)
    f = Money(fee, CCY)
    marks = {"AAPL": p}

    start_equity = acc.equity(marks)
    acc.apply_order(Order("o1", Side.BUY, "AAPL", qty, p, f))
    acc.apply_order(Order("o2", Side.SELL, "AAPL", qty, p, f))
    end_equity = acc.equity(marks)

    assert end_equity == start_equity - f - f
    assert acc.position("AAPL") == 0


@given(price=prices, qty=quantities, fee=fees)
@settings(max_examples=300)
def test_cash_plus_market_value_equals_equity(price, qty, fee):
    """The core accounting identity: cash + market value == equity."""
    acc = funded_account()
    p = Money(price, CCY)
    f = Money(fee, CCY)
    # Only buy if affordable, otherwise the invariant is trivially the cash.
    cost = p * qty + f
    if cost.amount <= acc.cash_balance(CCY).amount:
        acc.apply_order(Order("o1", Side.BUY, "AAPL", qty, p, f))

    marks = {"AAPL": p}
    market_value = p * acc.position("AAPL")
    assert acc.cash_balance(CCY) + market_value == acc.equity(marks)


@given(
    orders=st.lists(
        st.tuples(prices, quantities, fees),
        min_size=1,
        max_size=8,
    )
)
@settings(max_examples=200)
def test_replay_reconciles_with_live_state(orders):
    """Folding the append-only log reproduces the live derived state exactly."""
    acc = funded_account()
    for i, (price, qty, fee) in enumerate(orders):
        p = Money(price, CCY)
        f = Money(fee, CCY)
        cost = p * qty + f
        if cost.amount <= acc.cash_balance(CCY).amount:
            acc.apply_order(Order(f"o{i}", Side.BUY, "AAPL", qty, p, f))

    rebuilt = replay(acc.transactions, base_currency=CCY)
    assert rebuilt.cash_balance(CCY) == acc.cash_balance(CCY)
    assert rebuilt.position("AAPL") == acc.position("AAPL")


@given(price=prices, qty=quantities, fee=fees)
@settings(max_examples=200)
def test_idempotent_apply_never_double_spends(price, qty, fee):
    """Applying the same order id twice is a no-op the second time."""
    acc = funded_account()
    p = Money(price, CCY)
    f = Money(fee, CCY)
    order = Order("dup", Side.BUY, "AAPL", qty, p, f)

    acc.apply_order(order)
    cash_after_first = acc.cash_balance(CCY)
    pos_after_first = acc.position("AAPL")

    acc.apply_order(order)  # retry
    assert acc.cash_balance(CCY) == cash_after_first
    assert acc.position("AAPL") == pos_after_first


def test_cannot_spend_unavailable_cash():
    """Virtual cash cannot go negative."""
    acc = funded_account(starting=Decimal("100"))
    with pytest.raises(InsufficientCash):
        acc.apply_order(Order("o1", Side.BUY, "AAPL", Decimal("10"), cad("50"), cad("0")))
