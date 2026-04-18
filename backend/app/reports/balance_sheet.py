"""Balance sheet report.

Assets = Liabilities + Equity, as of a date. Current-period net income
(income minus expenses through the as-of date) is rolled into a synthetic
equity row "Current Year Earnings" so the equation holds without a formal
period close.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType, NormalBalance
from app.models.journal import JournalEntry, JournalLine, JournalStatus
from app.reports.basis import Basis
from app.schemas.reports import (
    BalanceSheetReport,
    BSSection,
    BSSectionRow,
)


def build_balance_sheet(
    session: Session,
    *,
    as_of_date: date,
    basis: Basis = Basis.ACCRUAL,
) -> BalanceSheetReport:
    """Build a balance sheet as of ``as_of_date`` on the given basis."""
    _ = basis  # Phase 1: toggle is a no-op.

    stmt = (
        select(JournalLine, Account)
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(JournalEntry.status == JournalStatus.POSTED)
        .where(JournalEntry.entry_date <= as_of_date)
    )

    balances: dict[Account, int] = {}
    for line, account in session.execute(stmt).all():
        if account.normal_balance() == NormalBalance.DEBIT:
            delta = line.debit_cents - line.credit_cents
        else:
            delta = line.credit_cents - line.debit_cents
        balances[account] = balances.get(account, 0) + delta

    # Split into sections.
    assets = _section(balances, AccountType.ASSET, "Assets")
    liabilities = _section(balances, AccountType.LIABILITY, "Liabilities")
    equity_rows, equity_total = _section_rows(balances, AccountType.EQUITY)

    # Current-year earnings: income - expenses through as_of_date.
    # (For a balance-sheet-as-of that falls mid-year this is literally YTD.
    # A future period-close flow will zero these into Retained Earnings.)
    current_earnings = 0
    for account, amount in balances.items():
        if account.type == AccountType.INCOME:
            current_earnings += amount
        elif account.type == AccountType.EXPENSE:
            current_earnings -= amount

    if current_earnings != 0:
        equity_rows.append(
            BSSectionRow(
                account_id=0,
                account_code="3999",
                account_name="Current Year Earnings",
                balance_cents=current_earnings,
            )
        )
        equity_total += current_earnings

    equity = BSSection(label="Equity", rows=equity_rows, subtotal_cents=equity_total)

    diff = assets.subtotal_cents - (liabilities.subtotal_cents + equity.subtotal_cents)
    return BalanceSheetReport(
        as_of_date=as_of_date,
        basis=basis,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        equation_difference_cents=diff,
        balanced=diff == 0,
    )


def _section_rows(
    balances: dict[Account, int], account_type: AccountType
) -> tuple[list[BSSectionRow], int]:
    rows: list[BSSectionRow] = []
    subtotal = 0
    for account, amount in sorted(balances.items(), key=lambda kv: kv[0].code):
        if account.type != account_type:
            continue
        if amount == 0:
            continue
        rows.append(
            BSSectionRow(
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                balance_cents=amount,
            )
        )
        subtotal += amount
    return rows, subtotal


def _section(
    balances: dict[Account, int], account_type: AccountType, label: str
) -> BSSection:
    rows, subtotal = _section_rows(balances, account_type)
    return BSSection(label=label, rows=rows, subtotal_cents=subtotal)
