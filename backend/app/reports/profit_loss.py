"""Profit & loss report.

Income minus expenses over a date window, with optional prior-period
comparison. Net income rolls to retained earnings at year-end (close flow
is a later phase).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType, NormalBalance
from app.models.journal import JournalEntry, JournalLine, JournalStatus
from app.reports.basis import Basis
from app.schemas.reports import (
    PLSection,
    PLSectionRow,
    ProfitLossReport,
)


def build_profit_loss(
    session: Session,
    *,
    start_date: date,
    end_date: date,
    basis: Basis = Basis.ACCRUAL,
    compare_prior_period: bool = False,
) -> ProfitLossReport:
    """Build a P&L for the window ``[start_date, end_date]``."""
    _ = basis  # Phase 1: toggle is a no-op; structure preserved for Phase 2.

    current = _period_totals(session, start_date, end_date)
    prior_map: dict[int, int] | None = None
    prior_net: int | None = None
    if compare_prior_period:
        delta = end_date - start_date + timedelta(days=1)
        prior_end = start_date - timedelta(days=1)
        prior_start = prior_end - delta + timedelta(days=1)
        prior = _period_totals(session, prior_start, prior_end)
        prior_map = {a.id: v for a, v in prior.items()}
        prior_net = _net_income(prior)

    income_rows: list[PLSectionRow] = []
    expense_rows: list[PLSectionRow] = []
    income_total = 0
    expense_total = 0
    for account, amount in sorted(current.items(), key=lambda kv: kv[0].code):
        prior_amount = prior_map.get(account.id) if prior_map is not None else None
        if account.type == AccountType.INCOME:
            income_rows.append(
                PLSectionRow(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    amount_cents=amount,
                    prior_amount_cents=prior_amount,
                )
            )
            income_total += amount
        elif account.type == AccountType.EXPENSE:
            expense_rows.append(
                PLSectionRow(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    amount_cents=amount,
                    prior_amount_cents=prior_amount,
                )
            )
            expense_total += amount

    return ProfitLossReport(
        start_date=start_date,
        end_date=end_date,
        basis=basis,
        income=PLSection(
            label="Income",
            rows=income_rows,
            subtotal_cents=income_total,
            prior_subtotal_cents=(
                sum(
                    (prior_map or {}).get(a.id, 0)
                    for a in current
                    if a.type == AccountType.INCOME
                )
                if prior_map is not None
                else None
            ),
        ),
        expenses=PLSection(
            label="Expenses",
            rows=expense_rows,
            subtotal_cents=expense_total,
            prior_subtotal_cents=(
                sum(
                    (prior_map or {}).get(a.id, 0)
                    for a in current
                    if a.type == AccountType.EXPENSE
                )
                if prior_map is not None
                else None
            ),
        ),
        net_income_cents=income_total - expense_total,
        prior_net_income_cents=prior_net,
    )


def _period_totals(
    session: Session, start_date: date, end_date: date
) -> dict[Account, int]:
    """Return signed amounts for each income/expense account in the window."""
    stmt = (
        select(JournalLine, JournalEntry, Account)
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(JournalEntry.status == JournalStatus.POSTED)
        .where(JournalEntry.entry_date >= start_date)
        .where(JournalEntry.entry_date <= end_date)
        .where(Account.type.in_((AccountType.INCOME, AccountType.EXPENSE)))
    )
    totals: dict[Account, int] = {}
    for line, _entry, account in session.execute(stmt).all():
        if account.normal_balance() == NormalBalance.CREDIT:
            delta = line.credit_cents - line.debit_cents
        else:
            delta = line.debit_cents - line.credit_cents
        totals[account] = totals.get(account, 0) + delta
    # Drop zero-balance accounts.
    return {k: v for k, v in totals.items() if v != 0}


def _net_income(period: dict[Account, int]) -> int:
    total = 0
    for account, amount in period.items():
        if account.type == AccountType.INCOME:
            total += amount
        elif account.type == AccountType.EXPENSE:
            total -= amount
    return total
