"""Invoice and InvoiceLine models — AR sub-ledger.

An invoice is a bill-to-customer document. It starts life as a draft,
gets posted (status -> sent) which creates a journal entry that debits
Accounts Receivable and credits the revenue account(s) on its lines,
and then gets paid down via ``Payment`` / ``PaymentApplication`` rows
in ``payment.py``.

Status FSM (DB-enforced by ``trg_invoices_status_fsm``):

    draft --(post)--> sent --(payment)--> partial <--> paid
      |                 |                                 |
      |                 +-------(full payment)-----------+|
      |                                                   |
      +---(void)---> void <--(void)-- any non-draft ------+

- ``void`` is terminal: no outbound transitions.
- ``draft`` can only be the initial state; no status transitions
  back to ``draft``.

Header immutability (``trg_invoices_immutable_posted``): once status
leaves draft, every field except ``status`` and ``amount_paid_cents``
is frozen.

Line immutability: adding, updating, or deleting invoice_lines once
the parent invoice is non-draft is rejected by triggers.
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


class InvoiceStatus(str, enum.Enum):
    """Lifecycle of a customer invoice."""

    DRAFT = "draft"
    SENT = "sent"
    PARTIAL = "partial"
    PAID = "paid"
    VOID = "void"


class Invoice(CompanyBase):
    """Header for a bill-to-customer document."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("number", name="uq_invoices_number"),
        CheckConstraint(
            "status IN ('draft','sent','partial','paid','void')",
            name="ck_invoices_status_valid",
        ),
        CheckConstraint(
            "subtotal_cents >= 0 AND tax_total_cents >= 0 AND total_cents >= 0",
            name="ck_invoices_non_negative",
        ),
        CheckConstraint(
            "total_cents = subtotal_cents + tax_total_cents",
            name="ck_invoices_total_is_sum",
        ),
        CheckConstraint(
            "amount_paid_cents >= 0 AND amount_paid_cents <= total_cents",
            name="ck_invoices_paid_within_total",
        ),
        CheckConstraint(
            "terms IN ('net_15','net_30','net_60','due_on_receipt','custom')",
            name="ck_invoices_terms_valid",
        ),
        Index("ix_invoices_customer", "customer_id"),
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Human-readable invoice number, e.g. 'INV-0001'. Unique per company.",
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
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
        default=InvoiceStatus.DRAFT.value,
        doc="One of: draft, sent, partial, paid, void.",
    )
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        doc="The JE that posted this invoice. NULL while in draft.",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lines: Mapped[list[InvoiceLine]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.line_number",
    )

    @property
    def balance_cents(self) -> int:
        """Outstanding amount: total minus applied payments."""
        return self.total_cents - self.amount_paid_cents

    def __repr__(self) -> str:
        return (
            f"Invoice(id={self.id}, number={self.number!r}, "
            f"status={self.status}, total_cents={self.total_cents})"
        )


class InvoiceLine(CompanyBase):
    """One line item on an invoice."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity_milli > 0",
            name="ck_invoice_lines_qty_positive",
        ),
        CheckConstraint(
            "unit_price_cents >= 0",
            name="ck_invoice_lines_price_non_negative",
        ),
        CheckConstraint(
            "tax_amount_cents >= 0 AND amount_cents >= 0",
            name="ck_invoice_lines_amounts_non_negative",
        ),
        Index("ix_invoice_lines_invoice", "invoice_id"),
        Index("ix_invoice_lines_tax_code", "tax_code_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-based position within the invoice.",
    )
    item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Optional pointer to the catalog item this line describes.",
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Revenue account credited when the invoice posts.",
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

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")

    def __repr__(self) -> str:
        return (
            f"InvoiceLine(invoice={self.invoice_id}, #{self.line_number}, "
            f"qty={self.quantity_milli / 1000:.3f}, amount={self.amount_cents})"
        )


def compute_line_amount_cents(quantity_milli: int, unit_price_cents: int) -> int:
    """Banker's-rounded integer amount: quantity * price.

    Both inputs are already scaled-integer. The result is in cents.
    ``(qty_milli * price_cents) / 1000`` yields cents with 0 fractional
    precision; ``round()`` handles the tie-to-even case (banker's
    rounding) so repeated computations don't drift in one direction.
    """
    product = quantity_milli * unit_price_cents
    # Banker's rounding on the division by 1000.
    quotient, remainder = divmod(product, 1000)
    if remainder < 500:
        return quotient
    if remainder > 500:
        return quotient + 1
    # Exactly 500: round to even.
    return quotient + (quotient & 1)


def compute_tax_amount_cents(amount_cents: int, rate_bps: int) -> int:
    """Banker's-rounded tax amount from an amount and a rate in bps."""
    product = amount_cents * rate_bps
    quotient, remainder = divmod(product, 10000)
    if remainder < 5000:
        return quotient
    if remainder > 5000:
        return quotient + 1
    return quotient + (quotient & 1)
