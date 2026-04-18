"""Journal-entry services: create draft, post, void, list.

Void is implemented as an entry reversal: a new entry with swapped
debits/credits pointing at the original via ``reversal_of_id``. The
original is preserved; its status flips to VOID.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.account import Account
from app.models.audit import AuditAction
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus
from app.schemas.journal import JournalEntryCreate
from app.services.audit import record_audit


def _load(session: Session, entry_id: int) -> JournalEntry:
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.id == entry_id)
        .options(selectinload(JournalEntry.lines))
    )
    entry = session.execute(stmt).scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"journal entry {entry_id} not found",
        )
    return entry


def list_entries(
    session: Session,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    account_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[JournalEntry], int]:
    from sqlalchemy import func

    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
    )
    count_stmt = select(func.count()).select_from(JournalEntry)
    if start_date is not None:
        stmt = stmt.where(JournalEntry.entry_date >= start_date)
        count_stmt = count_stmt.where(JournalEntry.entry_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(JournalEntry.entry_date <= end_date)
        count_stmt = count_stmt.where(JournalEntry.entry_date <= end_date)
    if account_id is not None:
        stmt = stmt.where(
            JournalEntry.lines.any(JournalLine.account_id == account_id)
        )
        count_stmt = count_stmt.where(
            JournalEntry.lines.any(JournalLine.account_id == account_id)
        )
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            (JournalEntry.reference.ilike(pattern))
            | (JournalEntry.memo.ilike(pattern))
        )
        count_stmt = count_stmt.where(
            (JournalEntry.reference.ilike(pattern))
            | (JournalEntry.memo.ilike(pattern))
        )

    total = session.execute(count_stmt).scalar_one()
    entries = list(session.execute(stmt.limit(limit).offset(offset)).scalars().all())
    return entries, total


def get_entry(session: Session, entry_id: int) -> JournalEntry:
    return _load(session, entry_id)


def create_entry(
    session: Session,
    payload: JournalEntryCreate,
    *,
    actor: str | None = None,
) -> JournalEntry:
    # Verify all referenced accounts exist and are active.
    account_ids = [line.account_id for line in payload.lines]
    stmt = select(Account).where(Account.id.in_(account_ids))
    accounts = list(session.execute(stmt).scalars().all())
    found_ids = {a.id for a in accounts}
    missing = set(account_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account(s) not found: {sorted(missing)}",
        )
    inactive = [a.id for a in accounts if not a.is_active]
    if inactive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"account(s) are deactivated: {sorted(inactive)}",
        )

    assert payload.posting_date is not None  # set by the validator
    entry = JournalEntry(
        entry_date=payload.entry_date,
        posting_date=payload.posting_date,
        reference=payload.reference,
        memo=payload.memo,
        source_type=JournalSource.MANUAL,
        status=JournalStatus.DRAFT,
        created_by=actor,
    )
    entry.lines = [
        JournalLine(
            line_number=i + 1,
            account_id=line.account_id,
            debit_cents=line.debit_cents,
            credit_cents=line.credit_cents,
            memo=line.memo,
        )
        for i, line in enumerate(payload.lines)
    ]
    session.add(entry)
    session.flush()

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="journal_entry",
        entity_id=entry.id,
        after={
            "entry_date": entry.entry_date.isoformat(),
            "memo": entry.memo,
            "lines": [
                {"account_id": line.account_id, "dr": line.debit_cents, "cr": line.credit_cents}
                for line in entry.lines
            ],
        },
        actor=actor,
    )
    return entry


def post_entry(
    session: Session,
    entry_id: int,
    *,
    actor: str | None = None,
) -> JournalEntry:
    entry = _load(session, entry_id)
    if entry.status == JournalStatus.POSTED:
        return entry
    if entry.status == JournalStatus.VOID:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="voided entries cannot be posted",
        )
    if not entry.is_balanced():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"entry does not balance: debits={entry.total_debits()} "
                f"credits={entry.total_credits()}"
            ),
        )
    if len(entry.lines) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entry must have at least two lines",
        )
    entry.status = JournalStatus.POSTED
    session.flush()
    record_audit(
        session,
        action=AuditAction.POST,
        entity_type="journal_entry",
        entity_id=entry.id,
        actor=actor,
    )
    return entry


def void_entry(
    session: Session,
    entry_id: int,
    *,
    actor: str | None = None,
    memo: Optional[str] = None,
) -> JournalEntry:
    """Void a posted entry.

    Creates a reversing entry (debits and credits swapped) dated today,
    pointing at the original via ``reversal_of_id``. The original's
    status transitions to VOID.
    """
    from datetime import date as _date

    entry = _load(session, entry_id)
    if entry.status == JournalStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft entries should be deleted, not voided",
        )
    if entry.status == JournalStatus.VOID:
        return entry

    # Create the reversal as draft first, attach lines, then transition to
    # posted. Inserting lines on an already-posted entry would trip the
    # trg_journal_lines_no_insert_on_posted trigger.
    reversal = JournalEntry(
        entry_date=_date.today(),
        posting_date=_date.today(),
        reference=f"VOID-{entry.reference or entry.id}",
        memo=memo or f"Reversal of entry {entry.id}",
        source_type=JournalSource.REVERSAL,
        status=JournalStatus.DRAFT,
        reversal_of_id=entry.id,
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
        for i, line in enumerate(entry.lines)
    ]
    session.add(reversal)
    session.flush()
    reversal.status = JournalStatus.POSTED
    entry.status = JournalStatus.VOID
    session.flush()

    record_audit(
        session,
        action=AuditAction.VOID,
        entity_type="journal_entry",
        entity_id=entry.id,
        after={"reversed_by_entry_id": reversal.id},
        actor=actor,
    )
    return entry


def delete_draft(
    session: Session, entry_id: int, *, actor: str | None = None
) -> None:
    entry = _load(session, entry_id)
    if entry.status != JournalStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only draft entries can be deleted; void posted entries instead",
        )
    session.delete(entry)
    session.flush()
    record_audit(
        session,
        action=AuditAction.DELETE,
        entity_type="journal_entry",
        entity_id=entry_id,
        actor=actor,
    )
