"""Declarative base and shared column types.

``DecimalType`` keeps money and quantities exact across engines: PostgreSQL has a
real ``NUMERIC``, but SQLite (used in tests) would otherwise round-trip through a
float. We quantize on the way out so a stored ``100.00`` never comes back as
``100.00000001`` — the same no-float-money discipline as the domain layer.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DecimalType(TypeDecorator):
    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int = 28, scale: int = 8, **kw):
        self._scale = scale
        super().__init__(precision=precision, scale=scale, asdecimal=True, **kw)

    def process_bind_param(self, value, dialect):
        return None if value is None else Decimal(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(value).quantize(Decimal(1).scaleb(-self._scale))


# Money is quantized to cents (scale 4 leaves headroom for fees/FX); share
# quantities allow fractional shares (scale 8).
Money4 = DecimalType(scale=4)
Qty8 = DecimalType(scale=8)
