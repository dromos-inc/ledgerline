"""BillPayment request/response schemas.

Mirror of ``app.schemas.payment``. Differences:

- ``vendor_id`` replaces ``customer_id``.
- ``payout_account_id`` replaces ``deposit_account_id`` (semantics:
  money LEAVES this asset account).
- Applications target bills instead of invoices.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_METHODS = ("check", "ach", "card", "wire", "cash", "other")


class BillPaymentApplicationCreate(BaseModel):
    """One bill a bill_payment is being applied to."""

    bill_id: int
    amount_cents: int = Field(..., gt=0)
    discount_cents: int = Field(default=0, ge=0)
    writeoff_cents: int = Field(default=0, ge=0)


class BillPaymentApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_payment_id: int
    bill_id: int
    amount_cents: int
    discount_cents: int
    writeoff_cents: int


class BillPaymentCreate(BaseModel):
    """Create a posted bill_payment with its applications.

    Applications must sum to <= ``amount_cents``. The difference is
    unapplied (vendor credit). Each application's
    ``amount_cents + discount_cents + writeoff_cents`` must not exceed
    the target bill's outstanding balance.
    """

    vendor_id: int
    payment_date: date
    amount_cents: int = Field(..., gt=0)
    payout_account_id: int
    method: Optional[str] = None
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    applications: list[BillPaymentApplicationCreate] = Field(default_factory=list)

    @field_validator("method")
    @classmethod
    def _method_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in _ALLOWED_METHODS:
            allowed = ", ".join(_ALLOWED_METHODS)
            raise ValueError(f"method must be one of: {allowed}")
        return v


class BillPaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    payment_date: date
    amount_cents: int
    payout_account_id: int
    method: Optional[str]
    reference: Optional[str]
    memo: Optional[str]
    journal_entry_id: int
    status: str
    applied_cents: int
    unapplied_cents: int
    applications: list[BillPaymentApplicationRead]

    @classmethod
    def from_orm_payment(cls, p) -> BillPaymentRead:
        return cls(
            id=p.id,
            vendor_id=p.vendor_id,
            payment_date=p.payment_date,
            amount_cents=p.amount_cents,
            payout_account_id=p.payout_account_id,
            method=p.method,
            reference=p.reference,
            memo=p.memo,
            journal_entry_id=p.journal_entry_id,
            status=p.status,
            applied_cents=p.applied_cents,
            unapplied_cents=p.unapplied_cents,
            applications=[
                BillPaymentApplicationRead.model_validate(a) for a in p.applications
            ],
        )