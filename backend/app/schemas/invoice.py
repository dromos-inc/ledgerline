"""Invoice request/response schemas."""

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


class InvoiceLineCreate(BaseModel):
    """One line of a draft invoice.

    ``account_id`` may be omitted IF ``item_id`` is provided AND that
    item has a ``default_income_account_id``. The service layer
    resolves the effective account.
    """

    item_id: Optional[int] = None
    account_id: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=512)
    quantity_milli: int = Field(..., gt=0)
    unit_price_cents: int = Field(..., ge=0)
    tax_code_id: Optional[int] = None


class InvoiceLineRead(BaseModel):
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


class InvoiceCreate(BaseModel):
    """Create a draft invoice. Status starts at 'draft'."""

    number: str = Field(..., min_length=1, max_length=32)
    customer_id: int
    invoice_date: date
    due_date: date
    terms: str = Field(default="net_30", max_length=32)
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    lines: list[InvoiceLineCreate] = Field(..., min_length=1)

    @field_validator("terms")
    @classmethod
    def _terms_ok(cls, v: str) -> str:
        return _validate_terms(v)

    @field_validator("due_date")
    @classmethod
    def _due_after_invoice(cls, v: date, info) -> date:
        inv = info.data.get("invoice_date")
        if inv is not None and v < inv:
            raise ValueError("due_date must be on or after invoice_date")
        return v


class InvoiceUpdate(BaseModel):
    """Patch a draft invoice. Posted invoices cannot be updated via this."""

    customer_id: Optional[int] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    terms: Optional[str] = Field(default=None, max_length=32)
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    lines: Optional[list[InvoiceLineCreate]] = None

    @field_validator("terms")
    @classmethod
    def _terms_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_terms(v)


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    customer_id: int
    invoice_date: date
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
    sent_at: Optional[datetime]
    lines: list[InvoiceLineRead]

    @classmethod
    def from_orm_invoice(cls, inv) -> InvoiceRead:
        return cls(
            id=inv.id,
            number=inv.number,
            customer_id=inv.customer_id,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            terms=inv.terms,
            reference=inv.reference,
            memo=inv.memo,
            subtotal_cents=inv.subtotal_cents,
            tax_total_cents=inv.tax_total_cents,
            total_cents=inv.total_cents,
            amount_paid_cents=inv.amount_paid_cents,
            balance_cents=inv.balance_cents,
            status=inv.status,
            journal_entry_id=inv.journal_entry_id,
            sent_at=inv.sent_at,
            lines=[InvoiceLineRead.model_validate(line) for line in inv.lines],
        )
