"""Sub-ledger reconciliation canary.

PRD and Phase 2 plan §4.3: at any moment, the AR control account's
balance should equal the net of open invoice balances AND unapplied
customer credits. If the two ever drift, the ledger is corrupted.

Phase 2 / S2 extends this to the AP side: same invariant, mirrored
signs. The AP control balance (a credit-normal liability) equals open
bill balances netted against unapplied bill_payment credits.

This report isn't a trigger — the invariant spans several tables
(accounts, invoices, payments, bills, bill_payments) which triggers
can't cheaply express. Instead we expose a single HTTP endpoint the
UI (or a monitoring probe) can hit periodically. Non-zero differences
surface immediately and the test suite asserts zero after every state
transition.

Why unapplied credits matter
----------------------------
A payment always credits AR for the full ``amount_cents`` (see
``app/services/payment.py``), whether or not every cent lands on an
invoice. Only the *applied* portion reduces the corresponding
invoice's ``amount_paid_cents``; the unapplied remainder is customer
credit that will consume future invoices.

Example (AR): customer pays $1000 against an $800 invoice. Applied
$800, unapplied $200.

- GL: Dr AR $800 (invoice) + Cr AR $1000 (payment) = net $-200 on AR.
- Invoice row: total $800, amount_paid $800 → balance $0.
- Without the unapplied adjustment the formula would read
  ``sub_ledger = $0`` and flag a $-200 drift that isn't real.

Correct sub-ledger expression:
``SUM(open invoice balances) - SUM(unapplied payment credits)``.
That equals the AR control balance when the books are consistent.

AP mirror
---------
Same math, opposite sign convention:

- AP control is a liability (credit normal). A bill that debits AP for
  $800 while a bill_payment credits AP for $1000 leaves AP at
  $800 Dr - $1000 Cr = -$200. The $-200 on AP represents a vendor
  credit (they've prepaid against future bills).
- Open bill balances sum to $0 after the bill is paid; unapplied
  bill_payment credit is $200.
- Effective AP sub-ledger = $0 - $200 = -$200 = AP control. ✓
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.bill import Bill
from app.models.bill_payment import BillPayment, BillPaymentApplication
from app.models.invoice import Invoice
from app.models.journal import JournalEntry, JournalLine, JournalStatus
from app.models.payment import Payment, PaymentApplication


@dataclass
class ReconciliationReport:
    as_of_date: date
    # AR side
    ar_sub_ledger_cents: int
    ar_control_balance_cents: int
    ar_unapplied_credits_cents: int
    ar_difference_cents: int
    ar_control_account_code: str | None
    ar_control_account_id: int | None
    # AP side (Phase 2 / S2)
    ap_sub_ledger_cents: int
    ap_control_balance_cents: int
    ap_unapplied_credits_cents: int
    ap_difference_cents: int
    ap_control_account_code: str | None
    ap_control_account_id: int | None


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
    non-void payments dated on or before as_of_date."""
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


def _sum_open_bill_balances(session: Session, as_of_date: date) -> int:
    """Sum (total - amount_paid) across non-void, non-draft bills
    dated on or before as_of_date."""
    stmt = (
        select(
            func.coalesce(
                func.sum(Bill.total_cents - Bill.amount_paid_cents), 0
            )
        )
        .where(Bill.status.in_(("open", "partial", "paid")))
        .where(Bill.bill_date <= as_of_date)
    )
    return int(session.execute(stmt).scalar_one())


def _sum_unapplied_bill_payment_credits(session: Session, as_of_date: date) -> int:
    """Unapplied vendor credit: SUM(bill_payment.amount - applied) across
    non-void bill_payments dated on or before as_of_date.

    A bill_payment row's ``amount_cents`` is what the AP control
    account was debited by the payment JE; ``SUM(applications)`` is
    what bill-side balances were reduced by. The difference is money
    we've sent the vendor that hasn't been absorbed by a bill yet —
    vendor credit for future bills.
    """
    applied_subq = (
        select(
            BillPaymentApplication.bill_payment_id.label("bill_payment_id"),
            func.coalesce(func.sum(BillPaymentApplication.amount_cents), 0).label(
                "applied_total"
            ),
        )
        .group_by(BillPaymentApplication.bill_payment_id)
        .subquery()
    )
    stmt = (
        select(
            func.coalesce(
                func.sum(
                    BillPayment.amount_cents
                    - func.coalesce(applied_subq.c.applied_total, 0)
                ),
                0,
            )
        )
        .select_from(BillPayment)
        .outerjoin(
            applied_subq, applied_subq.c.bill_payment_id == BillPayment.id
        )
        .where(BillPayment.status != "void")
        .where(BillPayment.payment_date <= as_of_date)
    )
    return int(session.execute(stmt).scalar_one())


def build_reconciliation(
    session: Session,
    *,
    as_of_date: date,
) -> ReconciliationReport:
    # AR side
    ar = session.execute(
        select(Account).where(Account.role == "ar_control")
    ).scalar_one_or_none()
    ar_sub = _sum_open_invoice_balances(session, as_of_date)
    ar_unapplied = _sum_unapplied_payment_credits(session, as_of_date)
    if ar is None:
        ar_control_bal = 0
        ar_diff = ar_sub - ar_unapplied
        ar_id = None
        ar_code = None
    else:
        ar_control_bal = _sum_control_balance(session, ar.id, as_of_date)
        ar_diff = ar_control_bal - (ar_sub - ar_unapplied)
        ar_id = ar.id
        ar_code = ar.code

    # AP side
    ap = session.execute(
        select(Account).where(Account.role == "ap_control")
    ).scalar_one_or_none()
    ap_sub = _sum_open_bill_balances(session, as_of_date)
    ap_unapplied = _sum_unapplied_bill_payment_credits(session, as_of_date)
    if ap is None:
        ap_control_bal = 0
        ap_diff = ap_sub - ap_unapplied
        ap_id = None
        ap_code = None
    else:
        # AP is credit-normal: a liability. The debit-minus-credit
        # formula yields a negative number for a healthy AP balance
        # (e.g. -$800 when we owe a vendor $800). To match the
        # sub-ledger convention (open bills are positive), we negate
        # the control balance before comparing.
        ap_control_bal = -_sum_control_balance(session, ap.id, as_of_date)
        ap_diff = ap_control_bal - (ap_sub - ap_unapplied)
        ap_id = ap.id
        ap_code = ap.code

    return ReconciliationReport(
        as_of_date=as_of_date,
        ar_sub_ledger_cents=ar_sub,
        ar_control_balance_cents=ar_control_bal,
        ar_unapplied_credits_cents=ar_unapplied,
        ar_difference_cents=ar_diff,
        ar_control_account_code=ar_code,
        ar_control_account_id=ar_id,
        ap_sub_ledger_cents=ap_sub,
        ap_control_balance_cents=ap_control_bal,
        ap_unapplied_credits_cents=ap_unapplied,
        ap_difference_cents=ap_diff,
        ap_control_account_code=ap_code,
        ap_control_account_id=ap_id,
    )