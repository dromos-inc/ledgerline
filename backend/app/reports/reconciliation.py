"""Sub-ledger reconciliation canary.

PRD and Phase 2 plan §4.3: at any moment, the AR control account's
balance should equal the sum of open invoice balances. Same for AP.
If the two ever drift, the ledger is corrupted.

This report isn't a trigger — the invariant spans two tables
(accounts vs. invoices) which triggers can't cheaply express. Instead
we expose a single HTTP endpoint the UI (or a monitoring probe) can
hit periodically. Non-zero differences surface immediately and the
test suite asserts zero after every state transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.invoice import Invoice
from app.models.journal import JournalEntry, JournalLine, JournalStatus


@dataclass
class ReconciliationReport:
    as_of_date: date
    ar_sub_ledger_cents: int
    ar_control_balance_cents: int
    ar_difference_cents: int
    ar_control_account_code: str | None
    ar_control_account_id: int | None


def _sum_control_balance(session: Session, account_id: int, as_of_date: date) -> int:
    """Debit - credit through the account from posted (non-void) JEs."""
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit_cents), 0)
            - func.coalesce(func.sum(JournalLine.credit_cents), 0)
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalLine.account_id == account_id)
        .where(JournalEntry.status == JournalStatus.POSTED)
        .where(JournalEntry.entry_date <= as_of_date)
    )
    return int(session.execute(stmt).scalar_one())


def _sum_open_invoice_balances(session: Session, as_of_date: date) -> int:
    """Sum (total - amount_paid) across non-void, non-draft invoices
    dated on or before as_of_date."""
    stmt = (
        select(
            func.coalesce(
                func.sum(Invoice.total_cents - Invoice.amount_paid_cents), 0
            )
        )
        .where(Invoice.status.in_(("sent", "partial", "paid")))
        .where(Invoice.invoice_date <= as_of_date)
    )
    return int(session.execute(stmt).scalar_one())


def build_reconciliation(
    session: Session,
    *,
    as_of_date: date,
) -> ReconciliationReport:
    # Find the AR control account.
    ar = session.execute(
        select(Account).where(Account.role == "ar_control")
    ).scalar_one_or_none()

    if ar is None:
        # No control account configured. Return a report that makes
        # that visible rather than failing outright.
        sub_ledger = _sum_open_invoice_balances(session, as_of_date)
        return ReconciliationReport(
            as_of_date=as_of_date,
            ar_sub_ledger_cents=sub_ledger,
            ar_control_balance_cents=0,
            ar_difference_cents=sub_ledger,
            ar_control_account_code=None,
            ar_control_account_id=None,
        )

    control_balance = _sum_control_balance(session, ar.id, as_of_date)
    # Sub-ledger: open invoice balances = total - amount_paid per
    # non-void invoice. We count 'paid' invoices too because their
    # contribution to both sides cancels (total - paid = 0), keeping
    # the difference clean.
    sub_ledger = _sum_open_invoice_balances(session, as_of_date)
    difference = control_balance - sub_ledger
    return ReconciliationReport(
        as_of_date=as_of_date,
        ar_sub_ledger_cents=sub_ledger,
        ar_control_balance_cents=control_balance,
        ar_difference_cents=difference,
        ar_control_account_code=ar.code,
        ar_control_account_id=ar.id,
    )
