"""Contact models — customers (AR side) and vendors (AP side).

Customers are whom the business invoices. Vendors are whom it pays
bills to. The two tables have nearly identical shape; they live in
the same module so the mirror is visible at a glance.

Phase 2 / S1 ships only the Customer side. The Vendor model lands in
the S2 (AP) commit; the vendors table already exists (migration 0002)
so the Vendor class will compose onto the existing schema without a
new migration.

Both contacts:

- Carry a user-facing ``code`` (e.g. "CUST-0042") separate from the
  integer primary key. Lets CSV import/export reference contacts by a
  stable human-readable id.
- Default to ``net_30`` terms unless overridden. The set of allowed
  term codes is fixed at the DB layer via CHECK constraint.
- Can soft-deactivate via ``is_active``. Hard deletion is blocked once
  any invoice (S1) or bill (S2) references the contact — a trigger
  will enforce that after the invoices/bills tables ship in migration
  0003/0004.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import CompanyBase

_ALLOWED_TERMS = ("net_15", "net_30", "net_60", "due_on_receipt", "custom")


class Customer(CompanyBase):
    """A party the business bills. Parent of invoices and payments."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("code", name="uq_customers_code"),
        CheckConstraint(
            "default_terms IN "
            "('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_customers_terms_valid",
        ),
        Index("ix_customers_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="User-facing short identifier, e.g. 'CUST-0042'.",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    billing_address: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    shipping_address: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    default_terms: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="net_30",
        doc="One of: " + ", ".join(_ALLOWED_TERMS),
    )
    default_income_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        doc=(
            "Income account to pre-select when creating an invoice line "
            "for this customer. Falls back to the item's default when an "
            "item is chosen."
        ),
    )
    default_tax_code_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_codes.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Tax code to pre-select on invoice lines for this customer.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"Customer(id={self.id}, code={self.code!r}, name={self.name!r})"
