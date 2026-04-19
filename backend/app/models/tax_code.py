"""Tax code model.

A tax code carries a rate stored as basis points (10000 = 100%) and
points at the liability account where tax collected accumulates.
Rates are immutable once any posted invoice line references the code
(enforced by trigger ``trg_tax_codes_rate_immutable`` when migration
0003 ships). Until then, the Phase 1 invoice_line table doesn't exist,
so the Phase 2 trigger body only enforces the non-negative range.

This model ships in Phase 2 / S1 because the ``customers`` table has
a foreign key to ``tax_codes``. SQLAlchemy needs the model for the
FK edge in its metadata graph, even though no service or API
surfaces creation until S3 lands.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import CompanyBase


class TaxCode(CompanyBase):
    """A named tax rate that can be applied to invoice and bill lines."""

    __tablename__ = "tax_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tax_codes_code"),
        CheckConstraint(
            "rate_bps >= 0 AND rate_bps < 10000",
            name="ck_tax_codes_rate_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="Short identifier, e.g. 'TX-STATE', 'GST', 'NONE'.",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="Human-readable name, e.g. 'Texas State Sales Tax'.",
    )
    rate_bps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc=(
            "Rate in basis points. 625 = 6.25%, 0 = 0%. Stored integer to "
            "avoid floating-point rounding in tax math. Immutable once "
            "referenced by a posted invoice line (trigger in 0003)."
        ),
    )
    payable_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Liability account where tax collected accumulates.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        pct = self.rate_bps / 100
        return f"TaxCode(id={self.id}, code={self.code!r}, rate={pct:.2f}%)"
