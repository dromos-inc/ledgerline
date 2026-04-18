"""Per-account register: ordered transactions with running balance."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, NormalBalance
from app.models.journal import JournalEntry, JournalLine, JournalStatus
from app.schemas.register import Register, RegisterRow


def build_register(
    session: Session,
    account_id: int,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Register:
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"account {account_id} not found",
        )

    # Voided entries stay in the register (their reversal is a separate
    # posted entry). Skipping void but showing the reversal would
    # double-count in the opposite direction. Showing both nets to zero,
    # which is the accounting reality.
    visible_statuses = (JournalStatus.POSTED, JournalStatus.VOID)

    # Opening balance: sum of all visible lines BEFORE start_date.
    opening = 0
    if start_date is not None:
        prior_stmt = (
            select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .where(JournalLine.account_id == account_id)
            .where(JournalEntry.entry_date < start_date)
            .where(JournalEntry.status.in_(visible_statuses))
        )
        for line, _entry in session.execute(prior_stmt).all():
            opening += _signed_amount(account.normal_balance(), line)

    # Window: visible lines in [start_date, end_date].
    window_stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account_id)
        .where(JournalEntry.status.in_(visible_statuses))
    )
    if start_date is not None:
        window_stmt = window_stmt.where(JournalEntry.entry_date >= start_date)
    if end_date is not None:
        window_stmt = window_stmt.where(JournalEntry.entry_date <= end_date)
    window_stmt = window_stmt.order_by(
        JournalEntry.entry_date, JournalEntry.id, JournalLine.line_number
    )

    rows: list[RegisterRow] = []
    running = opening
    for line, entry in session.execute(window_stmt).all():
        running += _signed_amount(account.normal_balance(), line)
        rows.append(
            RegisterRow(
                entry_id=entry.id,
                line_id=line.id,
                entry_date=entry.entry_date,
                posting_date=entry.posting_date,
                reference=entry.reference,
                memo=entry.memo,
                line_memo=line.memo,
                debit_cents=line.debit_cents,
                credit_cents=line.credit_cents,
                running_balance_cents=running,
            )
        )

    return Register(
        account_id=account.id,
        account_code=account.code,
        account_name=account.name,
        opening_balance_cents=opening,
        rows=rows,
        closing_balance_cents=running,
    )


def _signed_amount(normal: NormalBalance, line: JournalLine) -> int:
    """Convert a line's (debit, credit) into a signed contribution to the
    running balance, using the account's normal balance side.

    For a debit-normal account (asset, expense): +debit, -credit.
    For a credit-normal account (liability, equity, income): -debit, +credit.
    """
    if normal == NormalBalance.DEBIT:
        return line.debit_cents - line.credit_cents
    return line.credit_cents - line.debit_cents
