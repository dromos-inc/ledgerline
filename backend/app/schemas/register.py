"""Account register (per-account transaction list with running balance)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class RegisterRow(BaseModel):
    entry_id: int
    line_id: int
    entry_date: date
    posting_date: date
    reference: Optional[str]
    memo: Optional[str]
    line_memo: Optional[str]
    debit_cents: int
    credit_cents: int
    running_balance_cents: int


class Register(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    opening_balance_cents: int
    rows: list[RegisterRow]
    closing_balance_cents: int
