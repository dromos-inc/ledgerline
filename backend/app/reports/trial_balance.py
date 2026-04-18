"""Trial balance: every account with a non-zero balance as of a date."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, NormalBalance
from app.models.journal import JournalEntry, JournalLine, JournalStatus
from app.reports.basis import Basis
from app.schemas.reports import (
    TrialBalanceReport,
    TrialBalanceRow,
)


def build_trial_balance(
    session: Session,
    *,
    as_of_date: date,
    basis: Basis = Basis.ACCRUAL,
    include_zero: bool = False,
) -> TrialBalanceReport:
    """Build a trial balance as of ``as_of_date`` on the given basis.

    For Phase 1 (manual JEs only), ``basis`` has no effect. The parameter
    is accepted for API symmetry with P&L and balance sheet.
    """
    _ = basis  # reserved for Phase 2+

    stmt = (
        select(JournalLine, JournalEntry, Account)
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(JournalEntry.status == JournalStatus.POSTED)
        .where(JournalEntry.entry_date <= as_of_date)
    )

    totals: dict[int, dict[str, int | Account]] = {}
    for line, _entry, account in session.execute(stmt).all():
        row = totals.setdefault(
            account.id,
            {"account": account, "debit": 0, "credit": 0},
        )
        row["debit"] = int(row["debit"]) + line.debit_cents  # type: ignore[assignment]
        row["credit"] = int(row["credit"]) + line.credit_cents  # type: ignore[assignment]

    rows: list[TrialBalanceRow] = []
    total_debits = 0
    total_credits = 0
    for bucket in totals.values():
        account: Account = bucket["account"]  # type: ignore[assignment]
        dr = int(bucket["debit"])
        cr = int(bucket["credit"])
        net = dr - cr
        if account.normal_balance() == NormalBalance.DEBIT:
            debit_balance = max(net, 0)
            credit_balance = max(-net, 0)
        else:
            credit_balance = max(-net, 0)
            debit_balance = max(net, 0)

        if not include_zero and debit_balance == 0 and credit_balance == 0:
            continue

        rows.append(
            TrialBalanceRow(
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                account_type=account.type,
                debit_cents=debit_balance,
                credit_cents=credit_balance,
            )
        )
        total_debits += debit_balance
        total_credits += credit_balance

    rows.sort(key=lambda r: r.account_code)

    return TrialBalanceReport(
        as_of_date=as_of_date,
        basis=basis,
        rows=rows,
        total_debit_cents=total_debits,
        total_credit_cents=total_credits,
        balanced=total_debits == total_credits,
    )
