"""Reconciliation — independently rebuild state from the append-only log and
assert it matches the derived caches.

This is the safety net that turns "trust me, the caches are right" into a
checkable property. Run it on a schedule (Phase 4) or in tests: any divergence
between the folded ``transactions`` log and the ``positions`` / ``cash_balances``
tables is a caught bug, not silent corruption.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashBalance, Position, Transaction


@dataclass
class ReconResult:
    ok: bool
    discrepancies: list[str] = field(default_factory=list)


def reconcile(db: Session, portfolio_id: uuid.UUID) -> ReconResult:
    expected_cash: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    expected_pos: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))

    for tx in db.scalars(
        select(Transaction).where(Transaction.portfolio_id == portfolio_id)
    ):
        if tx.cash_delta is not None:
            expected_cash[tx.cash_currency] += Decimal(tx.cash_delta)
        if tx.quantity_delta is not None and tx.instrument_id is not None:
            expected_pos[tx.instrument_id] += Decimal(tx.quantity_delta)

    discrepancies: list[str] = []

    stored_cash = {
        cb.currency: Decimal(cb.amount)
        for cb in db.scalars(
            select(CashBalance).where(CashBalance.portfolio_id == portfolio_id)
        )
    }
    for ccy, expected in expected_cash.items():
        actual = stored_cash.get(ccy, Decimal("0"))
        if expected != actual:
            discrepancies.append(f"cash[{ccy}]: log={expected} cache={actual}")

    stored_pos = {
        p.instrument_id: Decimal(p.quantity)
        for p in db.scalars(
            select(Position).where(Position.portfolio_id == portfolio_id)
        )
    }
    for inst_id, expected in expected_pos.items():
        actual = stored_pos.get(inst_id, Decimal("0"))
        if expected != actual:
            discrepancies.append(f"position[{inst_id}]: log={expected} cache={actual}")

    return ReconResult(ok=not discrepancies, discrepancies=discrepancies)
