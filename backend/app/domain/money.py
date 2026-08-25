"""Money value object.

Rule #1 of a ledger: never represent money as a float. ``0.1 + 0.2 != 0.3`` in
binary floating point, and in a ledger that rounding error is money appearing or
vanishing. We use :class:`decimal.Decimal` quantized to cents, and we forbid
arithmetic across currencies so a CAD balance can never silently absorb USD.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Union

CENTS = Decimal("0.01")
SUPPORTED_CURRENCIES = frozenset({"CAD", "USD"})

Numeric = Union["Money", Decimal, int, str]


class CurrencyMismatch(ValueError):
    """Raised when two Money values of different currencies are combined."""


@dataclass(frozen=True, order=True)
class Money:
    """An immutable amount in a single currency, quantized to cents."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency: {self.currency!r}")
        # Frozen dataclass: bypass the setattr guard to normalise the amount.
        object.__setattr__(self, "amount", self._q(self.amount))

    @staticmethod
    def _q(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_EVEN)

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(Decimal("0"), currency)

    def _check(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(f"{self.currency} vs {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: Decimal | int | str) -> "Money":
        return Money(self.amount * Decimal(factor), self.currency)

    __rmul__ = __mul__

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
