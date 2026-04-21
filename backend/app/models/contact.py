"""Contact models — customers (AR side) and vendors (AP side).

Customers are whom the business invoices. Vendors are whom it pays
bills to. The two tables have nearly identical shape; they live in
the same module so the mirror is visible at a glance.

Phase 2 / S1 shipped the Customer side (AR). Phase 2 / S2 adds Vendor
(AP). The ``vendors`` table already exists as of migration 0002; this
module composes a Vendor class onto that schema without a new
migration. Migration 0004 adds the ``trg_vendors_no_delete_with_bills``
trigger that mirrors the customer-side protection.

Both contacts:

- Carry a user-facing ``code`` (e.g. "CUST-0042", "VEND-0042")
  separate from the integer primary key. Lets CSV import/export
  reference contacts by a stable human-readable id.
- Default to ``net_30`` terms unless overridden. The set of allowed
  term codes is fixed at the DB layer via CHECK constraint.
- Can soft-deactivate via ``is_active``. Hard deletion is blocked once
  any invoice (S1) or bill (S2) references the contact.
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


class Vendor(CompanyBase):
    """A party the business pays bills to. Parent of bills and bill_payments."""

    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint("code", name="uq_vendors_code"),
        CheckConstraint(
            "default_terms IN "
            "('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_vendors_terms_valid",
        ),
        Index("ix_vendors_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="User-facing short identifier, e.g. 'VEND-0042'.",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    billing_address: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    default_terms: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="net_30",
        doc="One of: " + ", ".join(_ALLOWED_TERMS),
    )
    default_expense_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        doc=(
            "Expense account to pre-select when creating a bill line for "
            "this vendor. Falls back to the item's default when an item "
            "is chosen."
        ),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_1099: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flags the vendor for 1099-NEC / 1099-MISC inclusion. The PDF "
        "export of 1099s is deferred to Phase 4; the flag is captured now "
        "so data is ready when the export ships.",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"Vendor(id={self.id}, code={self.code!r}, name={self.name!r})"
