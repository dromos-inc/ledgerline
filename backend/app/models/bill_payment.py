"""BillPayment and BillPaymentApplication models — AP sub-ledger.

A BillPayment is money sent to a vendor, leaving from a chosen payout
account (usually a bank or cash account). A BillPaymentApplication
attaches some portion of a bill_payment to a specific bill, optionally
netted by an early-pay discount or a write-off.

Mirror of ``Payment`` / ``PaymentApplication`` on the AR side. Design
notes carry over verbatim:

- BillPayments post immediately on create. The service layer builds the
  matching journal entry (Dr AP, Cr payout account) in the same
  transaction and links it via ``journal_entry_id`` (NOT NULL).
- BillPayments void by reversal: create a reversing JE, flip status to
  ``void``. A trigger rejects DELETE on posted or voided rows.
- One BillPayment can split across many bills via many applications.
  UNIQUE(bill_payment_id, bill_id) forbids duplicate applications of
  the same payment to the same bill.
- Unapplied portion of a bill_payment =
  ``amount_cents - SUM(applications.amount_cents)``. Represents
  prepayment / vendor credit to consume against future bills.
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


class BillPaymentStatus(str, enum.Enum):
    """Lifecycle of a vendor bill payment."""

    POSTED = "posted"
    VOID = "void"


class BillPayment(CompanyBase):
    """A single vendor bill payment."""

    __tablename__ = "bill_payments"
    __table_args__ = (
        CheckConstraint(
            "amount_cents > 0",
            name="ck_bill_payments_amount_positive",
        ),
        CheckConstraint(
            "status IN ('posted','void')",
            name="ck_bill_payments_status_valid",
        ),
        CheckConstraint(
            "method IS NULL OR method IN ('check','ach','card','wire','cash','other')",
            name="ck_bill_payments_method_valid",
        ),
        Index("ix_bill_payments_vendor", "vendor_id"),
        Index("ix_bill_payments_date", "payment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payout_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        doc="The asset account money leaves from (usually a bank account).",
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
        default=BillPaymentStatus.POSTED.value,
    )

    applications: Mapped[list[BillPaymentApplication]] = relationship(
        "BillPaymentApplication",
        back_populates="bill_payment",
        cascade="all, delete-orphan",
    )

    @property
    def applied_cents(self) -> int:
        """Sum of amount_cents across this bill_payment's applications."""
        return sum(a.amount_cents for a in self.applications)

    @property
    def unapplied_cents(self) -> int:
        """Portion of the bill_payment not yet attached to a bill."""
        return self.amount_cents - self.applied_cents

    def __repr__(self) -> str:
        return (
            f"BillPayment(id={self.id}, vendor={self.vendor_id}, "
            f"amount={self.amount_cents}, status={self.status})"
        )


class BillPaymentApplication(CompanyBase):
    """Links a BillPayment to a Bill it (partially) settles."""

    __tablename__ = "bill_payment_applications"
    __table_args__ = (
        UniqueConstraint(
            "bill_payment_id", "bill_id", name="uq_bill_payment_applications_pair"
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_bill_payment_applications_amount_positive",
        ),
        CheckConstraint(
            "discount_cents >= 0 AND writeoff_cents >= 0",
            name="ck_bill_payment_applications_discount_non_negative",
        ),
        Index("ix_bill_payment_applications_bill", "bill_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_payment_id: Mapped[int] = mapped_column(
        ForeignKey("bill_payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bill_id: Mapped[int] = mapped_column(
        ForeignKey("bills.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    writeoff_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    bill_payment: Mapped[BillPayment] = relationship(
        "BillPayment", back_populates="applications"
    )

    def __repr__(self) -> str:
        return (
            f"BillPaymentApplication(bill_payment={self.bill_payment_id}, "
            f"bill={self.bill_id}, amount={self.amount_cents})"
        )