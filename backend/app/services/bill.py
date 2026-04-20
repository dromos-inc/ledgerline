"""Bill services: draft CRUD, post (auto-JE), void.

Mirror of ``app.services.invoice`` on the AP side. The ``post``
operation:

1. Loads the AP control account by ``role='ap_control'``.
2. Builds a JournalEntry in DRAFT with ``source_type='bill'``.
3. Adds lines: one debit per bill line to its expense account for
   ``amount_cents``; one debit per taxable bill line to the tax code's
   ``payable_account_id`` for ``tax_amount_cents`` (input-tax
   treatment; jurisdictions with non-reclaimable tax should gross-up
   the expense account and set ``tax_code_id=NULL``); one credit to
   AP for ``total_cents``. Net: Dr = Cr.
4. Transitions the JournalEntry to POSTED (trigger verifies balance).
5. Links ``bill.journal_entry_id`` and transitions ``bill.status`` to
   ``'open'``. Captures ``approved_at`` / ``approved_by``.

``void`` produces a reversing JournalEntry (debits/credits swapped),
transitions the bill to ``'void'``, and refuses if any bill_payment
applications still point at the bill.

Phase 2 / S2 note on tax on bills
---------------------------------
The debit-tax-to-payable-account shape above only makes accounting
sense in jurisdictions with a VAT/GST-style input-tax reclaim mechanic.
For US sales tax on inputs, tax paid to vendors is typically folded
into the expense (non-reclaimable). This service supports both:

- Callers who want the reclaim treatment pass ``tax_code_id`` on the
  line; the JE debits the payable account (reducing the output tax
  liability, which is the economic meaning of input-tax reclaim).
- Callers who want the gross-up treatment omit ``tax_code_id`` and
  pre-add tax to ``unit_price_cents``. No tax line appears in the JE.

Phase 2 / S2 tests exercise the no-tax path primarily. S3 (items +
tax codes) will layer on the real per-jurisdiction configuration.
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
from app.models.bill import Bill, BillLine, BillStatus
from app.models.bill_payment import BillPaymentApplication
from app.models.contact import Vendor
from app.models.invoice import (
    compute_line_amount_cents,
    compute_tax_amount_cents,
)
from app.models.item import Item
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus
from app.models.tax_code import TaxCode
from app.schemas.bill import BillCreate, BillLineCreate, BillUpdate
from app.services.audit import record_audit

_ALLOWED_LINE_ACCOUNT_TYPES = {AccountType.EXPENSE, AccountType.ASSET}


def _load_bill(session: Session, bill_id: int) -> Bill:
    stmt = (
        select(Bill)
        .where(Bill.id == bill_id)
        .options(selectinload(Bill.lines))
    )
    bill = session.execute(stmt).scalar_one_or_none()
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"bill {bill_id} not found",
        )
    return bill


def _load_vendor_active(session: Session, vendor_id: int) -> Vendor:
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"vendor {vendor_id} not found",
        )
    if not vendor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"vendor {vendor_id} is deactivated",
        )
    return vendor


def _resolve_line_account_id(
    session: Session, line: BillLineCreate
) -> tuple[int, Optional[int]]:
    """Return (account_id, tax_code_id) after resolving item defaults.

    Lines can omit ``account_id`` if they provide an ``item_id`` whose
    item has a ``default_expense_account_id``. Otherwise ``account_id``
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
            account_id = item.default_expense_account_id
        if tax_code_id is None:
            tax_code_id = item.default_tax_code_id

    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "line requires account_id (or item_id whose item has a "
                "default_expense_account_id)"
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
    if account.type not in _ALLOWED_LINE_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"bill line account {account_id} must be an expense or asset "
                f"account, got {account.type.value!r}"
            ),
        )
    return account_id, tax_code_id


def _build_lines(
    session: Session, lines_payload: list[BillLineCreate]
) -> tuple[list[BillLine], int, int]:
    """Return (line objects, subtotal_cents, tax_total_cents)."""
    built: list[BillLine] = []
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
            BillLine(
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


def list_bills(
    session: Session,
    *,
    vendor_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    start_date: Optional[_date] = None,
    end_date: Optional[_date] = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Bill], int]:
    from sqlalchemy import func

    stmt = (
        select(Bill)
        .options(selectinload(Bill.lines))
        .order_by(Bill.bill_date.desc(), Bill.id.desc())
    )
    count_stmt = select(func.count()).select_from(Bill)
    if vendor_id is not None:
        stmt = stmt.where(Bill.vendor_id == vendor_id)
        count_stmt = count_stmt.where(Bill.vendor_id == vendor_id)
    if status_filter is not None:
        stmt = stmt.where(Bill.status == status_filter)
        count_stmt = count_stmt.where(Bill.status == status_filter)
    if start_date is not None:
        stmt = stmt.where(Bill.bill_date >= start_date)
        count_stmt = count_stmt.where(Bill.bill_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Bill.bill_date <= end_date)
        count_stmt = count_stmt.where(Bill.bill_date <= end_date)
    total = session.execute(count_stmt).scalar_one()
    bills = list(
        session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    )
    return bills, total


def get_bill(session: Session, bill_id: int) -> Bill:
    return _load_bill(session, bill_id)


def create_draft(
    session: Session,
    payload: BillCreate,
    *,
    actor: str | None = None,
) -> Bill:
    _load_vendor_active(session, payload.vendor_id)
    lines, subtotal, tax_total = _build_lines(session, payload.lines)

    bill = Bill(
        number=payload.number,
        vendor_id=payload.vendor_id,
        bill_date=payload.bill_date,
        due_date=payload.due_date,
        terms=payload.terms,
        reference=payload.reference,
        memo=payload.memo,
        subtotal_cents=subtotal,
        tax_total_cents=tax_total,
        total_cents=subtotal + tax_total,
        status=BillStatus.DRAFT.value,
    )
    bill.lines = lines
    session.add(bill)
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"bill number {payload.number!r} already exists",
        ) from e

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="bill",
        entity_id=bill.id,
        after={"number": bill.number, "total_cents": bill.total_cents},
        actor=actor,
    )
    return bill


def update_draft(
    session: Session,
    bill_id: int,
    payload: BillUpdate,
    *,
    actor: str | None = None,
) -> Bill:
    bill = _load_bill(session, bill_id)
    if bill.status != BillStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only draft bills can be edited; post or void to change status",
        )

    updates = payload.model_dump(exclude_unset=True)
    new_lines_payload = updates.pop("lines", None)

    if "vendor_id" in updates:
        _load_vendor_active(session, updates["vendor_id"])

    for key, value in updates.items():
        setattr(bill, key, value)

    if new_lines_payload is not None:
        # Replace all lines atomically.
        for line in list(bill.lines):
            session.delete(line)
        session.flush()
        built, subtotal, tax_total = _build_lines(
            session, [BillLineCreate.model_validate(line) for line in new_lines_payload]
        )
        bill.lines = built
        bill.subtotal_cents = subtotal
        bill.tax_total_cents = tax_total
        bill.total_cents = subtotal + tax_total

    session.flush()
    record_audit(
        session,
        action=AuditAction.UPDATE,
        entity_type="bill",
        entity_id=bill.id,
        after={"total_cents": bill.total_cents},
        actor=actor,
    )
    return bill


def _load_ap_control(session: Session) -> Account:
    stmt = select(Account).where(Account.role == "ap_control")
    account = session.execute(stmt).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "no AP control account configured for this company; "
                "seed one with role='ap_control' (conventionally code 2000)"
            ),
        )
    return account


def post_bill(
    session: Session,
    bill_id: int,
    *,
    actor: str | None = None,
) -> Bill:
    bill = _load_bill(session, bill_id)
    if bill.status != BillStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"only draft bills can be posted; this one is {bill.status!r}",
        )
    if not bill.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bill must have at least one line to post",
        )

    ap = _load_ap_control(session)

    # Build the JE in DRAFT first, add lines, then transition to POSTED so
    # the balance-on-post trigger verifies everything at once.
    je = JournalEntry(
        entry_date=bill.bill_date,
        posting_date=bill.bill_date,
        reference=bill.number,
        memo=(bill.memo or f"Bill {bill.number}"),
        source_type=JournalSource.BILL,
        source_id=bill.id,
        status=JournalStatus.DRAFT,
        created_by=actor,
    )
    je_lines: list[JournalLine] = []
    next_line = 1
    for b_line in bill.lines:
        je_lines.append(
            JournalLine(
                line_number=next_line,
                account_id=b_line.account_id,
                debit_cents=b_line.amount_cents,
                credit_cents=0,
                memo=b_line.description,
            )
        )
        next_line += 1
        if b_line.tax_code_id is not None and b_line.tax_amount_cents > 0:
            tax_code = session.get(TaxCode, b_line.tax_code_id)
            assert tax_code is not None  # validated at create time
            je_lines.append(
                JournalLine(
                    line_number=next_line,
                    account_id=tax_code.payable_account_id,
                    debit_cents=b_line.tax_amount_cents,
                    credit_cents=0,
                    memo=f"Input tax {tax_code.code} on {b_line.description or bill.number}",
                )
            )
            next_line += 1
    je_lines.append(
        JournalLine(
            line_number=next_line,
            account_id=ap.id,
            debit_cents=0,
            credit_cents=bill.total_cents,
            memo=f"AP for bill {bill.number}",
        )
    )
    je.lines = je_lines
    session.add(je)
    session.flush()
    je.status = JournalStatus.POSTED
    session.flush()

    bill.journal_entry_id = je.id
    bill.status = BillStatus.OPEN.value
    bill.approved_at = datetime.now(timezone.utc)
    bill.approved_by = actor
    session.flush()

    record_audit(
        session,
        action=AuditAction.POST,
        entity_type="bill",
        entity_id=bill.id,
        after={"journal_entry_id": je.id, "status": bill.status},
        actor=actor,
    )
    return bill


def _has_active_applications(session: Session, bill_id: int) -> list[int]:
    """Return ids of applications from non-voided bill_payments.

    Voided bill_payments leave their BillPaymentApplication rows in
    place for history; they don't count against voiding a bill.
    """
    from app.models.bill_payment import BillPayment

    stmt = (
        select(BillPaymentApplication.id)
        .join(BillPayment, BillPayment.id == BillPaymentApplication.bill_payment_id)
        .where(BillPaymentApplication.bill_id == bill_id)
        .where(BillPayment.status != "void")
    )
    return list(session.execute(stmt).scalars().all())


def void_bill(
    session: Session,
    bill_id: int,
    *,
    actor: str | None = None,
) -> Bill:
    bill = _load_bill(session, bill_id)
    if bill.status == BillStatus.VOID.value:
        return bill
    if bill.status == BillStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft bills should be deleted, not voided",
        )
    applications = _has_active_applications(session, bill_id)
    if applications:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"cannot void bill {bill_id}: bill_payments are applied "
                f"(applications: {applications}). Void or unapply the "
                "bill_payments first."
            ),
        )

    # Reverse the posting JE.
    original_je = session.get(JournalEntry, bill.journal_entry_id)
    assert original_je is not None
    reversal = JournalEntry(
        entry_date=_date.today(),
        posting_date=_date.today(),
        reference=f"VOID-{bill.number}",
        memo=f"Void of bill {bill.number}",
        source_type=JournalSource.REVERSAL,
        source_id=bill.id,
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
    bill.status = BillStatus.VOID.value
    session.flush()

    record_audit(
        session,
        action=AuditAction.VOID,
        entity_type="bill",
        entity_id=bill.id,
        after={"reversed_by_entry_id": reversal.id},
        actor=actor,
    )
    return bill


def delete_draft(
    session: Session,
    bill_id: int,
    *,
    actor: str | None = None,
) -> None:
    bill = _load_bill(session, bill_id)
    if bill.status != BillStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only draft bills can be deleted; void posted ones instead",
        )
    session.delete(bill)
    session.flush()
    record_audit(
        session,
        action=AuditAction.DELETE,
        entity_type="bill",
        entity_id=bill_id,
        actor=actor,
    )