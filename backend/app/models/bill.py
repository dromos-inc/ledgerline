"""Bill and BillLine models — AP sub-ledger.

A bill is a vendor-owed document: the mirror of Invoice on the AP side.
It starts life as a draft, gets posted (status -> open) which creates a
journal entry that debits expense accounts and credits Accounts Payable,
and then gets paid down via ``BillPayment`` / ``BillPaymentApplication``
rows in ``bill_payment.py``.

Status FSM (DB-enforced by ``trg_bills_status_fsm``):

    draft --(post)--> open --(bill_payment)--> partial <--> paid
      |                 |                                     |
      |                 +---------(full payment)-------------+|
      |                                                        |
      +---(void)---> void <--(void)-- any non-draft -----------+

- ``void`` is terminal: no outbound transitions.
- ``draft`` can only be the initial state; no status transitions
  back to ``draft``.

The sole label difference vs. invoices: the initial posted state is
``'open'`` (bills "sit open" until paid) instead of ``'sent'`` (invoices
"go out"). Everything else — immutability guards, line freezes, void
mechanics — mirrors the AR side verbatim.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CompanyBase


class BillStatus(str, enum.Enum):
    """Lifecycle of a vendor bill."""

    DRAFT = "draft"
    OPEN = "open"
    PARTIAL = "partial"
    PAID = "paid"
    VOID = "void"


class Bill(CompanyBase):
    """Header for a vendor-owed document."""

    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint("number", name="uq_bills_number"),
        CheckConstraint(
            "status IN ('draft','open','partial','paid','void')",
            name="ck_bills_status_valid",
        ),
        CheckConstraint(
            "subtotal_cents >= 0 AND tax_total_cents >= 0 AND total_cents >= 0",
            name="ck_bills_non_negative",
        ),
        CheckConstraint(
            "total_cents = subtotal_cents + tax_total_cents",
            name="ck_bills_total_is_sum",
        ),
        CheckConstraint(
            "amount_paid_cents >= 0 AND amount_paid_cents <= total_cents",
            name="ck_bills_paid_within_total",
        ),
        CheckConstraint(
            "terms IN ('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_bills_terms_valid",
        ),
        Index("ix_bills_vendor", "vendor_id"),
        Index("ix_bills_status", "status"),
        Index("ix_bills_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Human-readable bill number, e.g. 'BILL-0001'. Unique per company.",
    )
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    terms: Mapped[str] = mapped_column(String(32), nullable=False, default="net_30")
    reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    memo: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=BillStatus.DRAFT.value,
        doc="One of: draft, open, partial, paid, void.",
    )
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        doc="The JE that posted this bill. NULL while in draft.",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Set when a draft transitions to open.",
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Actor identifier captured at post time.",
    )

    lines: Mapped[list[BillLine]] = relationship(
        "BillLine",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLine.line_number",
    )

    @property
    def balance_cents(self) -> int:
        """Outstanding amount: total minus applied payments."""
        return self.total_cents - self.amount_paid_cents

    def __repr__(self) -> str:
        return (
            f"Bill(id={self.id}, number={self.number!r}, "
            f"status={self.status}, total_cents={self.total_cents})"
        )


class BillLine(CompanyBase):
    """One line item on a bill."""

    __tablename__ = "bill_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity_milli > 0",
            name="ck_bill_lines_qty_positive",
        ),
        CheckConstraint(
            "unit_price_cents >= 0",
            name="ck_bill_lines_price_non_negative",
        ),
        CheckConstraint(
            "tax_amount_cents >= 0 AND amount_cents >= 0",
            name="ck_bill_lines_amounts_non_negative",
        ),
        Index("ix_bill_lines_bill", "bill_id"),
        Index("ix_bill_lines_tax_code", "tax_code_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[int] = mapped_column(
        ForeignKey("bills.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-based position within the bill.",
    )
    item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Optional pointer to the catalog item this line describes.",
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Expense (or capex asset) account debited when the bill posts.",
    )
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    quantity_milli: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
        doc="Quantity in thousandths. 1000 = 1 unit, 500 = 0.5 unit.",
    )
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_code_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    tax_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Pre-tax line total: round(quantity_milli * unit_price_cents / 1000).",
    )

    bill: Mapped[Bill] = relationship("Bill", back_populates="lines")

    def __repr__(self) -> str:
        return (
            f"BillLine(bill={self.bill_id}, #{self.line_number}, "
            f"qty={self.quantity_milli / 1000:.3f}, amount={self.amount_cents})"
        )

