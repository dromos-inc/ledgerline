"""Journal entries and journal lines — the atomic unit of the ledger.

Every financial event eventually reduces to a ``JournalEntry`` with two
or more ``JournalLine`` rows that balance. Debits equal credits, always.

Integrity enforcement is layered:

- Per-line: CHECK constraints on the ``journal_lines`` table reject
  negative amounts, disallow both-sides-zero, and disallow both-sides-
  positive on the same line.
- Per-entry balance (sum(debits) = sum(credits)) is validated in the
  service layer when an entry transitions draft → posted. A SQL trigger
  provides a second line of defense (see ``app/db/triggers.sql``).
- Immutability: a trigger rejects UPDATEs to posted entries except the
  specific transitions we allow (``posted → void``).
- No hard deletes: a trigger rejects DELETE on posted entries and their
  lines.
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
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CompanyBase


class JournalStatus(str, enum.Enum):
    """Lifecycle of a journal entry."""

    DRAFT = "draft"
    POSTED = "posted"
    VOID = "void"


class JournalSource(str, enum.Enum):
    """Which feature produced this entry.

    Phase 1 only used MANUAL and REVERSAL. Phase 2 / S1 added INVOICE
    and PAYMENT for the AR sub-ledger; S2 adds BILL and BILL_PAYMENT
    for the AP side. The ``trg_accounts_control_no_direct_je`` trigger
    keys off ``source_type='manual'`` to forbid manual JEs against
    control accounts, so sub-ledger-generated JEs must carry a non-
    manual value here to land successfully.
    """

    MANUAL = "manual"
    REVERSAL = "reversal"
    INVOICE = "invoice"
    PAYMENT = "payment"
    BILL = "bill"
    BILL_PAYMENT = "bill_payment"


class JournalEntry(CompanyBase):
    """A balanced set of debit/credit lines, dated and posted as a unit."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','posted','void')",
            name="ck_journal_entries_status_valid",
        ),
        Index("ix_journal_entries_entry_date", "entry_date"),
        Index("ix_journal_entries_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Economic date of the transaction (i.e. when it 'happened').",
    )
    posting_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Accounting-period date. Usually equal to entry_date.",
    )
    reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    memo: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    source_type: Mapped[JournalSource] = mapped_column(
        SAEnum(
            JournalSource,
            native_enum=False,
            length=24,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=JournalSource.MANUAL,
    )
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[JournalStatus] = mapped_column(
        SAEnum(
            JournalStatus,
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=JournalStatus.DRAFT,
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reversal_of_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        doc=(
            "If this entry is a reversal of another entry, points at the "
            "original. Set when voiding a posted entry."
        ),
    )

    lines: Mapped[list[JournalLine]] = relationship(
        "JournalLine",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_number",
    )
    reversal_of: Mapped[Optional[JournalEntry]] = relationship(
        "JournalEntry",
        remote_side="JournalEntry.id",
    )

    def total_debits(self) -> int:
        return sum(line.debit_cents for line in self.lines)

    def total_credits(self) -> int:
        return sum(line.credit_cents for line in self.lines)

    def is_balanced(self) -> bool:
        return self.total_debits() == self.total_credits()

    def __repr__(self) -> str:
        return (
            f"JournalEntry(id={self.id}, date={self.entry_date}, "
            f"status={self.status}, lines={len(self.lines)})"
        )


class JournalLine(CompanyBase):
    """One debit-or-credit against a single account, part of a JE."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint(
            "debit_cents >= 0 AND credit_cents >= 0",
            name="ck_journal_lines_non_negative",
        ),
        CheckConstraint(
            "(debit_cents = 0 AND credit_cents > 0) OR "
            "(credit_cents = 0 AND debit_cents > 0)",
            name="ck_journal_lines_exactly_one_side",
        ),
        Index("ix_journal_lines_entry", "journal_entry_id"),
        Index("ix_journal_lines_account", "account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-based position of this line within its entry.",
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    debit_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credit_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memo: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    entry: Mapped[JournalEntry] = relationship("JournalEntry", back_populates="lines")

    def __repr__(self) -> str:
        return (
            f"JournalLine(entry={self.journal_entry_id}, #{self.line_number}, "
            f"acct={self.account_id}, dr={self.debit_cents}, cr={self.credit_cents})"
        )