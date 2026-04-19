"""Invoice services: draft CRUD, post (auto-JE), void.

The ``post`` operation is the interesting piece. It:

1. Loads the AR control account by ``role='ar_control'``.
2. Builds a JournalEntry in DRAFT with ``source_type='invoice'``.
3. Adds lines: one debit to AR for ``total_cents``; one credit per
   invoice line to that line's revenue account for ``amount_cents``;
   one credit per taxable invoice line to the tax code's
   ``payable_account_id`` for ``tax_amount_cents``. Net: Dr = Cr.
4. Transitions the JournalEntry to POSTED (trigger verifies balance).
5. Links ``invoice.journal_entry_id`` and transitions
   ``invoice.status`` to ``'sent'``.

``void`` produces a reversing JournalEntry (debits/credits swapped),
transitions the invoice to ``'void'``, and refuses if any payment
applications still point at the invoice.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.account import Account, AccountType
from app.models.audit import AuditAction
from app.models.contact import Customer
from app.models.invoice import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    compute_line_amount_cents,
    compute_tax_amount_cents,
)
from app.models.item import Item
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus
from app.models.payment import PaymentApplication
from app.models.tax_code import TaxCode
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate, InvoiceUpdate
from app.services.audit import record_audit


def _load_invoice(session: Session, invoice_id: int) -> Invoice:
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.lines))
    )
    invoice = session.execute(stmt).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"invoice {invoice_id} not found",
        )
    return invoice


def _load_customer_active(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"customer {customer_id} not found",
        )
    if not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"customer {customer_id} is deactivated",
        )
    return customer


def _resolve_line_account_id(
    session: Session, line: InvoiceLineCreate
) -> tuple[int, Optional[int]]:
    """Return (account_id, tax_code_id) after resolving item defaults.

    Lines can omit ``account_id`` if they provide an ``item_id`` whose
    item has a ``default_income_account_id``. Otherwise ``account_id``
    must be given explicitly. Tax-code falls back similarly.
    """
    account_id = line.account_id
    tax_code_id = line.tax_code_id
    if line.item_id is not None:
        item = session.get(Item, line.item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"item {line.item_id} not found",
            )
        if account_id is None:
            account_id = item.default_income_account_id
        if tax_code_id is None:
            tax_code_id = item.default_tax_code_id

    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "line requires account_id (or item_id whose item has a "
                "default_income_account_id)"
            ),
        )

    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account {account_id} not found",
        )
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account {account_id} is deactivated",
        )
    if account.type != AccountType.INCOME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"invoice line account {account_id} must be an income account, "
                f"got {account.type.value!r}"
            ),
        )
    return account_id, tax_code_id


def _build_lines(
    session: Session, lines_payload: list[InvoiceLineCreate]
) -> tuple[list[InvoiceLine], int, int]:
    """Return (line objects, subtotal_cents, tax_total_cents)."""
    built: list[InvoiceLine] = []
    subtotal = 0
    tax_total = 0
    tax_rate_cache: dict[int, int] = {}
    for i, line in enumerate(lines_payload, start=1):
        account_id, tax_code_id = _resolve_line_account_id(session, line)
        amount = compute_line_amount_cents(line.quantity_milli, line.unit_price_cents)
        tax_amount = 0
        if tax_code_id is not None:
            if tax_code_id not in tax_rate_cache:
                code = session.get(TaxCode, tax_code_id)
                if code is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"tax_code {tax_code_id} not found",
                    )
                tax_rate_cache[tax_code_id] = code.rate_bps
            tax_amount = compute_tax_amount_cents(
                amount, tax_rate_cache[tax_code_id]
            )
        built.append(
            InvoiceLine(
                line_number=i,
                item_id=line.item_id,
                account_id=account_id,
                description=line.description,
                quantity_milli=line.quantity_milli,
                unit_price_cents=line.unit_price_cents,
                tax_code_id=tax_code_id,
                tax_amount_cents=tax_amount,
                amount_cents=amount,
            )
        )
        subtotal += amount
        tax_total += tax_amount
    return built, subtotal, tax_total


def list_invoices(
    session: Session,
    *,
    customer_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    start_date: Optional[_date] = None,
    end_date: Optional[_date] = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Invoice], int]:
    from sqlalchemy import func

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    )
    count_stmt = select(func.count()).select_from(Invoice)
    if customer_id is not None:
        stmt = stmt.where(Invoice.customer_id == customer_id)
        count_stmt = count_stmt.where(Invoice.customer_id == customer_id)
    if status_filter is not None:
        stmt = stmt.where(Invoice.status == status_filter)
        count_stmt = count_stmt.where(Invoice.status == status_filter)
    if start_date is not None:
        stmt = stmt.where(Invoice.invoice_date >= start_date)
        count_stmt = count_stmt.where(Invoice.invoice_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Invoice.invoice_date <= end_date)
        count_stmt = count_stmt.where(Invoice.invoice_date <= end_date)
    total = session.execute(count_stmt).scalar_one()
    invoices = list(
        session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    )
    return invoices, total


def get_invoice(session: Session, invoice_id: int) -> Invoice:
    return _load_invoice(session, invoice_id)


def create_draft(
    session: Session,
    payload: InvoiceCreate,
    *,
    actor: str | None = None,
) -> Invoice:
    _load_customer_active(session, payload.customer_id)
    lines, subtotal, tax_total = _build_lines(session, payload.lines)

    invoice = Invoice(
        number=payload.number,
        customer_id=payload.customer_id,
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
        terms=payload.terms,
        reference=payload.reference,
        memo=payload.memo,
        subtotal_cents=subtotal,
        tax_total_cents=tax_total,
        total_cents=subtotal + tax_total,
        status=InvoiceStatus.DRAFT.value,
    )
    invoice.lines = lines
    session.add(invoice)
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"invoice number {payload.number!r} already exists",
        ) from e

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="invoice",
        entity_id=invoice.id,
        after={"number": invoice.number, "total_cents": invoice.total_cents},
        actor=actor,
    )
    return invoice


def update_draft(
    session: Session,
    invoice_id: int,
    payload: InvoiceUpdate,
    *,
    actor: str | None = None,
) -> Invoice:
    invoice = _load_invoice(session, invoice_id)
    if invoice.status != InvoiceStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only draft invoices can be edited; post or void to change status",
        )

    updates = payload.model_dump(exclude_unset=True)
    new_lines_payload = updates.pop("lines", None)

    if "customer_id" in updates:
        _load_customer_active(session, updates["customer_id"])

    for key, value in updates.items():
        setattr(invoice, key, value)

    if new_lines_payload is not None:
        # Replace all lines atomically.
        for line in list(invoice.lines):
            session.delete(line)
        session.flush()
        built, subtotal, tax_total = _build_lines(
            session, [InvoiceLineCreate.model_validate(line) for line in new_lines_payload]
        )
        invoice.lines = built
        invoice.subtotal_cents = subtotal
        invoice.tax_total_cents = tax_total
        invoice.total_cents = subtotal + tax_total

    session.flush()
    record_audit(
        session,
        action=AuditAction.UPDATE,
        entity_type="invoice",
        entity_id=invoice.id,
        after={"total_cents": invoice.total_cents},
        actor=actor,
    )
    return invoice


def _load_ar_control(session: Session) -> Account:
    stmt = select(Account).where(Account.role == "ar_control")
    account = session.execute(stmt).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "no AR control account configured for this company; "
                "seed one with role='ar_control' (conventionally code 1200)"
            ),
        )
    return account


def post_invoice(
    session: Session,
    invoice_id: int,
    *,
    actor: str | None = None,
) -> Invoice:
    invoice = _load_invoice(session, invoice_id)
    if invoice.status != InvoiceStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"only draft invoices can be posted; this one is {invoice.status!r}",
        )
    if not invoice.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invoice must have at least one line to post",
        )

    ar = _load_ar_control(session)

    # Build the JE in DRAFT first, add lines, then transition to POSTED so
    # the balance-on-post trigger verifies everything at once.
    je = JournalEntry(
        entry_date=invoice.invoice_date,
        posting_date=invoice.invoice_date,
        reference=invoice.number,
        memo=(invoice.memo or f"Invoice {invoice.number}"),
        source_type=JournalSource.INVOICE,
        source_id=invoice.id,
        status=JournalStatus.DRAFT,
        created_by=actor,
    )
    je_lines: list[JournalLine] = []
    je_lines.append(
        JournalLine(
            line_number=1,
            account_id=ar.id,
            debit_cents=invoice.total_cents,
            credit_cents=0,
            memo=f"AR for invoice {invoice.number}",
        )
    )
    next_line = 2
    for inv_line in invoice.lines:
        je_lines.append(
            JournalLine(
                line_number=next_line,
                account_id=inv_line.account_id,
                debit_cents=0,
                credit_cents=inv_line.amount_cents,
                memo=inv_line.description,
            )
        )
        next_line += 1
        if inv_line.tax_code_id is not None and inv_line.tax_amount_cents > 0:
            tax_code = session.get(TaxCode, inv_line.tax_code_id)
            assert tax_code is not None  # validated at create time
            je_lines.append(
                JournalLine(
                    line_number=next_line,
                    account_id=tax_code.payable_account_id,
                    debit_cents=0,
                    credit_cents=inv_line.tax_amount_cents,
                    memo=f"Tax {tax_code.code} on {inv_line.description or invoice.number}",
                )
            )
            next_line += 1
    je.lines = je_lines
    session.add(je)
    session.flush()
    je.status = JournalStatus.POSTED
    session.flush()

    invoice.journal_entry_id = je.id
    invoice.status = InvoiceStatus.SENT.value
    invoice.sent_at = datetime.now(timezone.utc)
    session.flush()

    record_audit(
        session,
        action=AuditAction.POST,
        entity_type="invoice",
        entity_id=invoice.id,
        after={"journal_entry_id": je.id, "status": invoice.status},
        actor=actor,
    )
    return invoice


def _has_active_applications(session: Session, invoice_id: int) -> list[int]:
    """Return ids of applications from non-voided payments.

    Voided payments leave their PaymentApplication rows in place for
    history; they don't count against voiding an invoice.
    """
    from app.models.payment import Payment

    stmt = (
        select(PaymentApplication.id)
        .join(Payment, Payment.id == PaymentApplication.payment_id)
        .where(PaymentApplication.invoice_id == invoice_id)
        .where(Payment.status != "void")
    )
    return list(session.execute(stmt).scalars().all())


def void_invoice(
    session: Session,
    invoice_id: int,
    *,
    actor: str | None = None,
) -> Invoice:
    invoice = _load_invoice(session, invoice_id)
    if invoice.status == InvoiceStatus.VOID.value:
        return invoice
    if invoice.status == InvoiceStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft invoices should be deleted, not voided",
        )
    applications = _has_active_applications(session, invoice_id)
    if applications:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"cannot void invoice {invoice_id}: payments are applied "
                f"(applications: {applications}). Void or unapply the "
                "payments first."
            ),
        )

    # Reverse the posting JE.
    original_je = session.get(JournalEntry, invoice.journal_entry_id)
    assert original_je is not None
    reversal = JournalEntry(
        entry_date=_date.today(),
        posting_date=_date.today(),
        reference=f"VOID-{invoice.number}",
        memo=f"Void of invoice {invoice.number}",
        source_type=JournalSource.REVERSAL,
        source_id=invoice.id,
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
    invoice.status = InvoiceStatus.VOID.value
    session.flush()

    record_audit(
        session,
        action=AuditAction.VOID,
        entity_type="invoice",
        entity_id=invoice.id,
        after={"reversed_by_entry_id": reversal.id},
        actor=actor,
    )
    return invoice


def delete_draft(
    session: Session,
    invoice_id: int,
    *,
    actor: str | None = None,
) -> None:
    invoice = _load_invoice(session, invoice_id)
    if invoice.status != InvoiceStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only draft invoices can be deleted; void posted ones instead",
        )
    session.delete(invoice)
    session.flush()
    record_audit(
        session,
        action=AuditAction.DELETE,
        entity_type="invoice",
        entity_id=invoice_id,
        actor=actor,
    )
