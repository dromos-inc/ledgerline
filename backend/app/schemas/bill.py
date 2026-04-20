"""Bill request/response schemas.

Mirror of ``app.schemas.invoice`` with these AP-side adjustments:

- ``vendor_id`` replaces ``customer_id``.
- ``bill_date`` replaces ``invoice_date``.
- ``due_date`` still validated to be on or after ``bill_date``.
- Bill-line ``account_id`` must resolve to an EXPENSE account (service
  layer enforces); invoice-line ``account_id`` must be INCOME.
- ``BillRead`` exposes ``approved_at`` / ``approved_by`` (captured at
  post time) and ``balance_cents`` (derived).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_TERMS = ("net_15", "net_30", "net_60", "due_on_receipt", "custom")


def _validate_terms(value: str) -> str:
    if value not in _ALLOWED_TERMS:
        allowed = ", ".join(_ALLOWED_TERMS)
        raise ValueError(f"terms must be one of: {allowed}")
    return value


class BillLineCreate(BaseModel):
    """One line of a draft bill.

    ``account_id`` may be omitted IF ``item_id`` is provided AND that
    item has a ``default_expense_account_id``. The service layer
    resolves the effective account.
    """

    item_id: Optional[int] = None
    account_id: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=512)
    quantity_milli: int = Field(..., gt=0)
    unit_price_cents: int = Field(..., ge=0)
    tax_code_id: Optional[int] = None


class BillLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_number: int
    item_id: Optional[int]
    account_id: int
    description: Optional[str]
    quantity_milli: int
    unit_price_cents: int
    tax_code_id: Optional[int]
    tax_amount_cents: int
    amount_cents: int


class BillCreate(BaseModel):
    """Create a draft bill. Status starts at 'draft'."""

    number: str = Field(..., min_length=1, max_length=32)
    vendor_id: int
    bill_date: date
    due_date: date
    terms: str = Field(default="net_30", max_length=32)
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    lines: list[BillLineCreate] = Field(..., min_length=1)

    @field_validator("terms")
    @classmethod
    def _terms_ok(cls, v: str) -> str:
        return _validate_terms(v)

    @field_validator("due_date")
    @classmethod
    def _due_after_bill(cls, v: date, info) -> date:
        bill = info.data.get("bill_date")
        if bill is not None and v < bill:
            raise ValueError("due_date must be on or after bill_date")
        return v


class BillUpdate(BaseModel):
    """Patch a draft bill. Posted bills cannot be updated via this."""

    vendor_id: Optional[int] = None
    bill_date: Optional[date] = None
    due_date: Optional[date] = None
    terms: Optional[str] = Field(default=None, max_length=32)
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    lines: Optional[list[BillLineCreate]] = None

    @field_validator("terms")
    @classmethod
    def _terms_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_terms(v)


class BillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    vendor_id: int
    bill_date: date
    due_date: date
    terms: str
    reference: Optional[str]
    memo: Optional[str]
    subtotal_cents: int
    tax_total_cents: int
    total_cents: int
    amount_paid_cents: int
    balance_cents: int
    status: str
    journal_entry_id: Optional[int]
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    lines: list[BillLineRead]

    @classmethod
    def from_orm_bill(cls, bill) -> BillRead:
        return cls(
            id=bill.id,
            number=bill.number,
            vendor_id=bill.vendor_id,
            bill_date=bill.bill_date,
            due_date=bill.due_date,
            terms=bill.terms,
            reference=bill.reference,
            memo=bill.memo,
            subtotal_cents=bill.subtotal_cents,
            tax_total_cents=bill.tax_total_cents,
            total_cents=bill.total_cents,
            amount_paid_cents=bill.amount_paid_cents,
            balance_cents=bill.balance_cents,
            status=bill.status,
            journal_entry_id=bill.journal_entry_id,
            approved_at=bill.approved_at,
            approved_by=bill.approved_by,
            lines=[BillLineRead.model_validate(line) for line in bill.lines],
        )