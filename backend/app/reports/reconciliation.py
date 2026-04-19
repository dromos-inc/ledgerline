"""Sub-ledger reconciliation canary.

PRD and Phase 2 plan §4.3: at any moment, the AR control account's
balance should equal the net of open invoice balances AND unapplied
customer credits. If the two ever drift, the ledger is corrupted.

This report isn't a trigger — the invariant spans three tables
(accounts, invoices, payments) which triggers can't cheaply express.
Instead we expose a single HTTP endpoint the UI (or a monitoring
probe) can hit periodically. Non-zero differences surface immediately
and the test suite asserts zero after every state transition.

Why unapplied credits matter
----------------------------
A payment always credits the AR control account for the full
``amount_cents`` (see ``app/services/payment.py``), whether or not
every cent lands on an invoice. Only the *applied* portion reduces
the corresponding invoice's ``amount_paid_cents``; the unapplied
remainder is customer credit that will consume future invoices.

Example: customer pays $1000 against an $800 invoice. Applied $800,
unapplied $200.

- GL: Dr AR $800 (invoice) + Cr AR $1000 (payment) = net $-200 on AR.
- Invoice row: total $800, amount_paid $800 → balance $0.
- Without the unapplied adjustment the formula would read
  ``sub_ledger = $0`` and flag a $-200 drift that isn't real.

The correct sub-ledger expression is therefore
``SUM(open invoice balances) - SUM(unapplied payment credits)``.
That equals the AR control balance when the books are consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.invoice import Invoice
from app.models.journal import JournalEntry, JournalLine, JournalStatus
from app.models.payment import Payment, PaymentApplication


@dataclass
class ReconciliationReport:
    as_of_date: date
    ar_sub_ledger_cents: int
    ar_control_balance_cents: int
    ar_unapplied_credits_cents: int
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


def _sum_unapplied_payment_credits(session: Session, as_of_date: date) -> int:
    """Unapplied customer credit: SUM(payment.amount - applied) across
    non-void payments dated on or before as_of_date.

    A payment row's ``amount_cents`` is what the AR control account
    was credited by the payment JE; ``SUM(applications.amount_cents)``
    is what the invoice-side balances were reduced by. The difference
    is money the customer has paid that hasn't attached to any
    invoice yet. It sits on AR as a negative (credit) balance.
    """
    applied_subq = (
        select(
            PaymentApplication.payment_id.label("payment_id"),
            func.coalesce(func.sum(PaymentApplication.amount_cents), 0).label(
                "applied_total"
            ),
        )
        .group_by(PaymentApplication.payment_id)
        .subquery()
    )
    stmt = (
        select(
            func.coalesce(
                func.sum(
                    Payment.amount_cents
                    - func.coalesce(applied_subq.c.applied_total, 0)
                ),
                0,
            )
        )
        .select_from(Payment)
        .outerjoin(applied_subq, applied_subq.c.payment_id == Payment.id)
        .where(Payment.status != "void")
        .where(Payment.payment_date <= as_of_date)
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

    sub_ledger = _sum_open_invoice_balances(session, as_of_date)
    unapplied = _sum_unapplied_payment_credits(session, as_of_date)

    if ar is None:
        # No control account configured. Return a report that makes
        # that visible rather than failing outright.
        return ReconciliationReport(
            as_of_date=as_of_date,
            ar_sub_ledger_cents=sub_ledger,
            ar_control_balance_cents=0,
            ar_unapplied_credits_cents=unapplied,
            ar_difference_cents=sub_ledger - unapplied,
            ar_control_account_code=None,
            ar_control_account_id=None,
        )

    control_balance = _sum_control_balance(session, ar.id, as_of_date)
    # Sub-ledger side: open invoice balances minus unapplied customer
    # credits (the AR side of a payment with unapplied portion reduces
    # the control account even though no invoice absorbs it yet).
    # In a healthy company: control == sub_ledger - unapplied.
    effective_sub_ledger = sub_ledger - unapplied
    difference = control_balance - effective_sub_ledger
    return ReconciliationReport(
        as_of_date=as_of_date,
        ar_sub_ledger_cents=sub_ledger,
        ar_control_balance_cents=control_balance,
        ar_unapplied_credits_cents=unapplied,
        ar_difference_cents=difference,
        ar_control_account_code=ar.code,
        ar_control_account_id=ar.id,
    )
