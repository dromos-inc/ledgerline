"""Cash vs. accrual basis helpers.

In Phase 1, the product has manual journal entries only, so cash and
accrual collapse to the same thing. The toggle is plumbed now anyway so
callers can pass it without knowing the phase, and Phase 2 (AR/AP) plugs
into this module without rippling through every report.
"""

from __future__ import annotations

import enum


class Basis(str, enum.Enum):
    CASH = "cash"
    ACCRUAL = "accrual"

    @classmethod
    def parse(cls, value: str | None) -> Basis:
        if value is None:
            return cls.ACCRUAL
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"basis must be 'cash' or 'accrual'; got {value!r}") from e
