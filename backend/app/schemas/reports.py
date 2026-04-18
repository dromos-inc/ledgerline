"""Report response schemas.

Separate module so UI and tests can import report shapes without pulling
in account or journal schemas.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.models.account import AccountType
from app.reports.basis import Basis

# --- Trial balance ---------------------------------------------------------


class TrialBalanceRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    debit_cents: int
    credit_cents: int


class TrialBalanceReport(BaseModel):
    as_of_date: date
    basis: Basis
    rows: list[TrialBalanceRow]
    total_debit_cents: int
    total_credit_cents: int
    balanced: bool


# --- Profit & loss ---------------------------------------------------------


class PLSectionRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    amount_cents: int
    prior_amount_cents: Optional[int] = None


class PLSection(BaseModel):
    label: str  # "Income" or "Expenses"
    rows: list[PLSectionRow]
    subtotal_cents: int
    prior_subtotal_cents: Optional[int] = None


class ProfitLossReport(BaseModel):
    start_date: date
    end_date: date
    basis: Basis
    income: PLSection
    expenses: PLSection
    net_income_cents: int
    prior_net_income_cents: Optional[int] = None


# --- Balance sheet ---------------------------------------------------------


class BSSectionRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    balance_cents: int


class BSSection(BaseModel):
    label: str  # "Assets", "Liabilities", "Equity"
    rows: list[BSSectionRow]
    subtotal_cents: int


class BalanceSheetReport(BaseModel):
    as_of_date: date
    basis: Basis
    assets: BSSection
    liabilities: BSSection
    equity: BSSection
    # Equation: Assets = Liabilities + Equity. This includes current-period
    # net income rolled into a synthetic "Current Year Earnings" equity row
    # so the equation balances even without a formal period close.
    equation_difference_cents: int
    balanced: bool
