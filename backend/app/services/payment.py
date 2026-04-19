"""Payment services: create (with applications) + void.

A payment receives money from a customer and applies some or all of
it to outstanding invoices. Creation is atomic: build the payment
header + applications + the journal entry that moves money from AR
into the deposit account, all in one session transaction.

JE shape on create:
    Dr deposit_account   amount_cents
      Cr AR control        amount_cents - SUM(discount) - SUM(writeoff)
    Dr Bad Debt Expense  SUM(writeoff)     (when > 0)
    Dr Discount Taken    SUM(discount)     (when > 0, expense account)

For Phase 2 / S1 we defer the separate discount/bad-debt accounts
behind an ``OPTIONAL`` switch: the plan §4.2 shows the full ledger
with those lines, but the default convention expects dedicated
accounts that we haven't seeded. Until dedicated discount / writeoff
accounts exist with known roles, we short-circuit: only apply the
net-of-adjustments amount to AR, and reject if the caller passes
non-zero discount/writeoff (clear 400 explaining that the feature
requires additional account setup). That keeps the happy path
simple and correct without half-building the full ledger shape.

Void reverses the entire JE and flips ``payment.status`` to 'void'.
Invoices this payment applied to have their ``amount_paid_cents``
rolled back and their ``status`` re-derived (partial <-> sent, paid
-> partial, etc).
"""

from __future__ import annotations

from datetime import date as _date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.account import Account, AccountType
from app.models.audit import AuditAction
from app.models.contact import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus
from app.models.payment import Payment, PaymentApplication, PaymentStatus
from app.schemas.payment import PaymentApplicationCreate, PaymentCreate
from app.services.audit import record_audit


def _load_payment(session: Session, payment_id: int) -> Payment:
    stmt = (
        select(Payment)
        .where(Payment.id == payment_id)
        .options(selectinload(Payment.applications))
    )
    payment = session.execute(stmt).scalar_one_or_none()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"payment {payment_id} not found",
        )
    return payment


def _load_ar_control(session: Session) -> Account:
    stmt = select(Account).where(Account.role == "ar_control")
    account = session.execute(stmt).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no AR control account configured (role='ar_control')",
        )
    return account


def _validate_deposit_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"deposit_account_id {account_id} not found",
        )
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"deposit account {account_id} is deactivated",
        )
    if account.type != AccountType.ASSET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"deposit account must be an asset (bank/cash), got "
                f"{account.type.value!r}"
            ),
        )
    return account


def _validate_applications(
    session: Session,
    applications: list[PaymentApplicationCreate],
    payment_amount: int,
) -> list[tuple[Invoice, PaymentApplicationCreate]]:
    """Load target invoices, verify each application doesn't over-apply,
    and verify the sum across applications fits inside payment amount.
    Returns [(invoice, application_payload), ...].
    """
    if not applications:
        return []

    # Phase 2 / S1 decision: reject non-zero discount/writeoff for now.
    # See module docstring.
    for app_payload in applications:
        if app_payload.discount_cents or app_payload.writeoff_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "discount_cents and writeoff_cents require dedicated "
                    "expense accounts; feature not yet configured. Apply "
                    "the payment without adjustments, or void + re-create "
                    "the invoice to reduce its total."
                ),
            )

    total_applied = sum(a.amount_cents for a in applications)
    if total_applied > payment_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"applications sum to {total_applied} cents which exceeds "
                f"payment amount {payment_amount} cents"
            ),
        )

    # Load each invoice and verify it's payable + balance covers this app.
    result: list[tuple[Invoice, PaymentApplicationCreate]] = []
    for app_payload in applications:
        invoice = session.get(Invoice, app_payload.invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invoice {app_payload.invoice_id} not found",
            )
        if invoice.status in (InvoiceStatus.DRAFT.value, InvoiceStatus.VOID.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"cannot apply payment to invoice {invoice.id} with "
                    f"status {invoice.status!r}"
                ),
            )
        if app_payload.amount_cents > invoice.balance_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"application amount {app_payload.amount_cents} exceeds "
                    f"invoice {invoice.id} balance {invoice.balance_cents}"
                ),
            )
        result.append((invoice, app_payload))
    return result


def _derive_invoice_status(invoice: Invoice) -> str:
    """Re-derive status from amount_paid_cents and total_cents.

    Called after any application change. Void is never auto-entered
    from this function; use void_invoice for that.
    """
    if invoice.status == InvoiceStatus.VOID.value:
        return InvoiceStatus.VOID.value
    if invoice.amount_paid_cents == 0:
        return InvoiceStatus.SENT.value
    if invoice.amount_paid_cents >= invoice.total_cents:
        return InvoiceStatus.PAID.value
    return InvoiceStatus.PARTIAL.value


def list_payments(
    session: Session,
    *,
    customer_id: Optional[int] = None,
    start_date: Optional[_date] = None,
    end_date: Optional[_date] = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Payment], int]:
    from sqlalchemy import func

    stmt = (
        select(Payment)
        .options(selectinload(Payment.applications))
        .order_by(Payment.payment_date.desc(), Payment.id.desc())
    )
    count_stmt = select(func.count()).select_from(Payment)
    if customer_id is not None:
        stmt = stmt.where(Payment.customer_id == customer_id)
        count_stmt = count_stmt.where(Payment.customer_id == customer_id)
    if start_date is not None:
        stmt = stmt.where(Payment.payment_date >= start_date)
        count_stmt = count_stmt.where(Payment.payment_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Payment.payment_date <= end_date)
        count_stmt = count_stmt.where(Payment.payment_date <= end_date)
    total = session.execute(count_stmt).scalar_one()
    payments = list(
        session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    )
    return payments, total


def get_payment(session: Session, payment_id: int) -> Payment:
    return _load_payment(session, payment_id)


def create_payment(
    session: Session,
    payload: PaymentCreate,
    *,
    actor: str | None = None,
) -> Payment:
    # Load customer (active check).
    customer = session.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"customer {payload.customer_id} not found",
        )
    if not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"customer {payload.customer_id} is deactivated",
        )
    deposit = _validate_deposit_account(session, payload.deposit_account_id)
    ar = _load_ar_control(session)
    application_targets = _validate_applications(
        session, payload.applications, payload.amount_cents
    )
    total_applied = sum(a.amount_cents for _, a in application_targets)

    # Build the JE first in DRAFT so we can attach lines before POSTED.
    je = JournalEntry(
        entry_date=payload.payment_date,
        posting_date=payload.payment_date,
        reference=payload.reference,
        memo=payload.memo or f"Payment from customer {customer.code}",
        source_type=JournalSource.PAYMENT,
        status=JournalStatus.DRAFT,
        created_by=actor,
    )
    je_lines: list[JournalLine] = [
        JournalLine(
            line_number=1,
            account_id=deposit.id,
            debit_cents=payload.amount_cents,
            credit_cents=0,
            memo=f"Deposit {payload.reference or ''}".strip(),
        ),
        JournalLine(
            line_number=2,
            account_id=ar.id,
            debit_cents=0,
            credit_cents=payload.amount_cents,
            memo="AR payment",
        ),
    ]
    je.lines = je_lines
    session.add(je)
    session.flush()
    je.status = JournalStatus.POSTED
    session.flush()

    # Build the Payment header.
    payment = Payment(
        customer_id=payload.customer_id,
        payment_date=payload.payment_date,
        amount_cents=payload.amount_cents,
        deposit_account_id=payload.deposit_account_id,
        method=payload.method,
        reference=payload.reference,
        memo=payload.memo,
        journal_entry_id=je.id,
        status=PaymentStatus.POSTED.value,
    )
    session.add(payment)
    session.flush()

    # Attach applications, update each target invoice.
    for invoice, app_payload in application_targets:
        application = PaymentApplication(
            payment_id=payment.id,
            invoice_id=invoice.id,
            amount_cents=app_payload.amount_cents,
            discount_cents=0,
            writeoff_cents=0,
        )
        session.add(application)
        invoice.amount_paid_cents += app_payload.amount_cents
        invoice.status = _derive_invoice_status(invoice)
    session.flush()

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="payment",
        entity_id=payment.id,
        after={
            "amount_cents": payment.amount_cents,
            "applied_cents": total_applied,
            "applications": [
                {"invoice_id": inv.id, "amount": a.amount_cents}
                for inv, a in application_targets
            ],
        },
        actor=actor,
    )
    return payment


def void_payment(
    session: Session,
    payment_id: int,
    *,
    actor: str | None = None,
) -> Payment:
    payment = _load_payment(session, payment_id)
    if payment.status == PaymentStatus.VOID.value:
        return payment

    # Roll back each application's effect on its invoice.
    for application in payment.applications:
        invoice = session.get(Invoice, application.invoice_id)
        if invoice is None:
            continue  # shouldn't happen with FK restrict
        invoice.amount_paid_cents -= application.amount_cents
        if invoice.amount_paid_cents < 0:
            invoice.amount_paid_cents = 0  # defensive
        # Only re-derive status if the invoice isn't itself void.
        if invoice.status != InvoiceStatus.VOID.value:
            invoice.status = _derive_invoice_status(invoice)

    # Reverse the JE.
    original_je = session.get(JournalEntry, payment.journal_entry_id)
    assert original_je is not None
    reversal = JournalEntry(
        entry_date=_date.today(),
        posting_date=_date.today(),
        reference=f"VOID-PMT-{payment.id}",
        memo=f"Void of payment {payment.id}",
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
    payment.status = PaymentStatus.VOID.value
    session.flush()

    record_audit(
        session,
        action=AuditAction.VOID,
        entity_type="payment",
        entity_id=payment.id,
        after={"reversed_by_entry_id": reversal.id},
        actor=actor,
    )
    return payment
