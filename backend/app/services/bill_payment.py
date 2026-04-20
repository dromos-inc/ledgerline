"""BillPayment services: create (with applications) + void.

Mirror of ``app.services.payment``. A bill_payment sends money to a
vendor and applies some or all of it to outstanding bills. Creation is
atomic: build the bill_payment header + applications + journal entry
that moves money from AP into the payout account (i.e. out of our
bank), all in one session transaction.

JE shape on create:
    Dr AP control        amount_cents
      Cr payout_account  amount_cents

Discount/writeoff handling is deferred to the same follow-up ticket
that gated them on the AR side (see module docstring in
``app/services/payment.py``). Callers passing non-zero
``discount_cents`` or ``writeoff_cents`` get a clear 400.

Void reverses the entire JE and flips ``bill_payment.status`` to
``'void'``. Bills this bill_payment applied to have their
``amount_paid_cents`` rolled back and their ``status`` re-derived
(partial <-> open, paid -> partial, etc).
"""

from __future__ import annotations

from datetime import date as _date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.account import Account, AccountType
from app.models.audit import AuditAction
from app.models.bill import Bill, BillStatus
from app.models.bill_payment import (
    BillPayment,
    BillPaymentApplication,
    BillPaymentStatus,
)
from app.models.contact import Vendor
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus
from app.schemas.bill_payment import BillPaymentApplicationCreate, BillPaymentCreate
from app.services.audit import record_audit


def _load_bill_payment(session: Session, payment_id: int) -> BillPayment:
    stmt = (
        select(BillPayment)
        .where(BillPayment.id == payment_id)
        .options(selectinload(BillPayment.applications))
    )
    payment = session.execute(stmt).scalar_one_or_none()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"bill_payment {payment_id} not found",
        )
    return payment


def _load_ap_control(session: Session) -> Account:
    stmt = select(Account).where(Account.role == "ap_control")
    account = session.execute(stmt).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no AP control account configured (role='ap_control')",
        )
    return account


def _validate_payout_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"payout_account_id {account_id} not found",
        )
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"payout account {account_id} is deactivated",
        )
    if account.type != AccountType.ASSET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"payout account must be an asset (bank/cash), got "
                f"{account.type.value!r}"
            ),
        )
    return account


def _validate_applications(
    session: Session,
    applications: list[BillPaymentApplicationCreate],
    payment_amount: int,
) -> list[tuple[Bill, BillPaymentApplicationCreate]]:
    """Load target bills, verify each application doesn't over-apply, and
    verify the sum across applications fits inside payment amount.
    Returns [(bill, application_payload), ...].
    """
    if not applications:
        return []

    # Phase 2 / S2 decision: reject non-zero discount/writeoff for now.
    # Mirrors S1's AR-side behavior.
    for app_payload in applications:
        if app_payload.discount_cents or app_payload.writeoff_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "discount_cents and writeoff_cents require dedicated "
                    "expense accounts; feature not yet configured. Apply "
                    "the bill_payment without adjustments, or void + "
                    "re-create the bill to reduce its total."
                ),
            )

    total_applied = sum(a.amount_cents for a in applications)
    if total_applied > payment_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"applications sum to {total_applied} cents which exceeds "
                f"bill_payment amount {payment_amount} cents"
            ),
        )

    # Load each bill and verify it's payable + balance covers this app.
    result: list[tuple[Bill, BillPaymentApplicationCreate]] = []
    for app_payload in applications:
        bill = session.get(Bill, app_payload.bill_id)
        if bill is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"bill {app_payload.bill_id} not found",
            )
        if bill.status in (BillStatus.DRAFT.value, BillStatus.VOID.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"cannot apply bill_payment to bill {bill.id} with "
                    f"status {bill.status!r}"
                ),
            )
        if app_payload.amount_cents > bill.balance_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"application amount {app_payload.amount_cents} exceeds "
                    f"bill {bill.id} balance {bill.balance_cents}"
                ),
            )
        result.append((bill, app_payload))
    return result


def _derive_bill_status(bill: Bill) -> str:
    """Re-derive bill status from amount_paid_cents and total_cents."""
    if bill.status == BillStatus.VOID.value:
        return BillStatus.VOID.value
    if bill.amount_paid_cents == 0:
        return BillStatus.OPEN.value
    if bill.amount_paid_cents >= bill.total_cents:
        return BillStatus.PAID.value
    return BillStatus.PARTIAL.value


def list_bill_payments(
    session: Session,
    *,
    vendor_id: Optional[int] = None,
    start_date: Optional[_date] = None,
    end_date: Optional[_date] = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[BillPayment], int]:
    from sqlalchemy import func

    stmt = (
        select(BillPayment)
        .options(selectinload(BillPayment.applications))
        .order_by(BillPayment.payment_date.desc(), BillPayment.id.desc())
    )
    count_stmt = select(func.count()).select_from(BillPayment)
    if vendor_id is not None:
        stmt = stmt.where(BillPayment.vendor_id == vendor_id)
        count_stmt = count_stmt.where(BillPayment.vendor_id == vendor_id)
    if start_date is not None:
        stmt = stmt.where(BillPayment.payment_date >= start_date)
        count_stmt = count_stmt.where(BillPayment.payment_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(BillPayment.payment_date <= end_date)
        count_stmt = count_stmt.where(BillPayment.payment_date <= end_date)
    total = session.execute(count_stmt).scalar_one()
    payments = list(
        session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    )
    return payments, total


def get_bill_payment(session: Session, payment_id: int) -> BillPayment:
    return _load_bill_payment(session, payment_id)


def create_bill_payment(
    session: Session,
    payload: BillPaymentCreate,
    *,
    actor: str | None = None,
) -> BillPayment:
    vendor = session.get(Vendor, payload.vendor_id)
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"vendor {payload.vendor_id} not found",
        )
    if not vendor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"vendor {payload.vendor_id} is deactivated",
        )
    payout = _validate_payout_account(session, payload.payout_account_id)
    ap = _load_ap_control(session)
    application_targets = _validate_applications(
        session, payload.applications, payload.amount_cents
    )
    total_applied = sum(a.amount_cents for _, a in application_targets)

    # Build the JE first in DRAFT so we can attach lines before POSTED.
    je = JournalEntry(
        entry_date=payload.payment_date,
        posting_date=payload.payment_date,
        reference=payload.reference,
        memo=payload.memo or f"Bill payment to vendor {vendor.code}",
        source_type=JournalSource.BILL_PAYMENT,
        status=JournalStatus.DRAFT,
        created_by=actor,
    )
    je_lines: list[JournalLine] = [
        JournalLine(
            line_number=1,
            account_id=ap.id,
            debit_cents=payload.amount_cents,
            credit_cents=0,
            memo="AP bill_payment",
        ),
        JournalLine(
            line_number=2,
            account_id=payout.id,
            debit_cents=0,
            credit_cents=payload.amount_cents,
            memo=f"Payout {payload.reference or ''}".strip(),
        ),
    ]
    je.lines = je_lines
    session.add(je)
    session.flush()
    je.status = JournalStatus.POSTED
    session.flush()

    # Build the BillPayment header.
    payment = BillPayment(
        vendor_id=payload.vendor_id,
        payment_date=payload.payment_date,
        amount_cents=payload.amount_cents,
        payout_account_id=payload.payout_account_id,
        method=payload.method,
        reference=payload.reference,
        memo=payload.memo,
        journal_entry_id=je.id,
        status=BillPaymentStatus.POSTED.value,
    )
    session.add(payment)
    session.flush()

    # Attach applications, update each target bill.
    for bill, app_payload in application_targets:
        application = BillPaymentApplication(
            bill_payment_id=payment.id,
            bill_id=bill.id,
            amount_cents=app_payload.amount_cents,
            discount_cents=0,
            writeoff_cents=0,
        )
        session.add(application)
        bill.amount_paid_cents += app_payload.amount_cents
        bill.status = _derive_bill_status(bill)
    session.flush()

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="bill_payment",
        entity_id=payment.id,
        after={
            "amount_cents": payment.amount_cents,
            "applied_cents": total_applied,
            "applications": [
                {"bill_id": b.id, "amount": a.amount_cents}
                for b, a in application_targets
            ],
        },
        actor=actor,
    )
    return payment


def void_bill_payment(
    session: Session,
    payment_id: int,
    *,
    actor: str | None = None,
) -> BillPayment:
    payment = _load_bill_payment(session, payment_id)
    if payment.status == BillPaymentStatus.VOID.value:
        return payment

    # Roll back each application's effect on its bill.
    for application in payment.applications:
        bill = session.get(Bill, application.bill_id)
        if bill is None:
            continue  # shouldn't happen with FK restrict
        bill.amount_paid_cents -= application.amount_cents
        if bill.amount_paid_cents < 0:
            bill.amount_paid_cents = 0  # defensive
        # Only re-derive status if the bill isn't itself void.
        if bill.status != BillStatus.VOID.value:
            bill.status = _derive_bill_status(bill)

    # Reverse the JE.
    original_je = session.get(JournalEntry, payment.journal_entry_id)
    assert original_je is not None
    reversal = JournalEntry(
        entry_date=_date.today(),
        posting_date=_date.today(),
        reference=f"VOID-BPMT-{payment.id}",
        memo=f"Void of bill_payment {payment.id}",
        source_type=JournalSource.REVERSAL,
        source_id=payment.id,
        status=JournalStatus.DRAFT,
        reversal_of_id=original_je.id,
        created_by=actor,
    )
    reversal.lines = [
        JournalLine(
            line_number=i + 1,
            account_id=line.account_id,
            debit_cents=line.credit_cents,
            credit_cents=line.debit_cents,
            memo=line.memo,
        )
        for i, line in enumerate(original_je.lines)
    ]
    session.add(reversal)
    session.flush()
    reversal.status = JournalStatus.POSTED
    payment.status = BillPaymentStatus.VOID.value
    session.flush()

    record_audit(
        session,
        action=AuditAction.VOID,
        entity_type="bill_payment",
        entity_id=payment.id,
        after={"reversed_by_entry_id": reversal.id},
        actor=actor,
    )
    return payment