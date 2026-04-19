"""Payment and PaymentApplication models — AR sub-ledger.

A Payment is money received from a customer, landing in a specified
deposit account (usually a bank or cash account). A PaymentApplication
attaches some portion of a payment to a specific invoice, optionally
netted by an early-pay discount or a write-off.

Design notes:

- Payments post immediately on create. The service layer builds the
  matching journal entry (Dr deposit account, Cr AR) in the same
  transaction and links it via ``journal_entry_id`` (NOT NULL).
- Payments void by reversal: create a reversing JE, flip status to
  ``void``. A trigger rejects DELETE on posted or voided payments.
- One Payment can split across many invoices via many
  PaymentApplications. The UNIQUE(payment_id, invoice_id) constraint
  forbids duplicate applications of the same payment to the same
  invoice; if you want to increase the applied amount, update the
  existing row.
- The unapplied portion of a payment is
  ``amount_cents - SUM(applications.amount_cents)``. A prepaid
  customer has an unapplied positive balance; the UI surfaces it so
  future invoices can consume the credit.
"""

from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CompanyBase


class PaymentStatus(str, enum.Enum):
    """Lifecycle of a customer payment."""

    POSTED = "posted"
    VOID = "void"


class Payment(CompanyBase):
    """A single customer payment deposit."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "amount_cents > 0",
            name="ck_payments_amount_positive",
        ),
        CheckConstraint(
            "status IN ('posted','void')",
            name="ck_payments_status_valid",
        ),
        CheckConstraint(
            "method IS NULL OR method IN ('check','ach','card','wire','cash','other')",
            name="ck_payments_method_valid",
        ),
        Index("ix_payments_customer", "customer_id"),
        Index("ix_payments_date", "payment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="The asset account the deposit lands in (usually a bank account).",
    )
    method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Check number, ACH confirmation, or similar.",
    )
    memo: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PaymentStatus.POSTED.value,
    )

    applications: Mapped[list[PaymentApplication]] = relationship(
        "PaymentApplication",
        back_populates="payment",
        cascade="all, delete-orphan",
    )

    @property
    def applied_cents(self) -> int:
        """Sum of amount_cents across this payment's applications."""
        return sum(a.amount_cents for a in self.applications)

    @property
    def unapplied_cents(self) -> int:
        """Portion of the payment not yet attached to an invoice."""
        return self.amount_cents - self.applied_cents

    def __repr__(self) -> str:
        return (
            f"Payment(id={self.id}, customer={self.customer_id}, "
            f"amount={self.amount_cents}, status={self.status})"
        )


class PaymentApplication(CompanyBase):
    """Links a Payment to an Invoice it (partially) settles."""

    __tablename__ = "payment_applications"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", "invoice_id", name="uq_payment_applications_pair"
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_payment_applications_amount_positive",
        ),
        CheckConstraint(
            "discount_cents >= 0 AND writeoff_cents >= 0",
            name="ck_payment_applications_discount_non_negative",
        ),
        Index("ix_payment_applications_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    writeoff_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    payment: Mapped[Payment] = relationship("Payment", back_populates="applications")

    def __repr__(self) -> str:
        return (
            f"PaymentApplication(payment={self.payment_id}, "
            f"invoice={self.invoice_id}, amount={self.amount_cents})"
        )
