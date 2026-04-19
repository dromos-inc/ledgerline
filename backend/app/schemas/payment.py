"""Payment request/response schemas."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_METHODS = ("check", "ach", "card", "wire", "cash", "other")


class PaymentApplicationCreate(BaseModel):
    """One invoice a payment is being applied to."""

    invoice_id: int
    amount_cents: int = Field(..., gt=0)
    discount_cents: int = Field(default=0, ge=0)
    writeoff_cents: int = Field(default=0, ge=0)


class PaymentApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: int
    invoice_id: int
    amount_cents: int
    discount_cents: int
    writeoff_cents: int


class PaymentCreate(BaseModel):
    """Create a posted payment with its applications.

    Applications must sum to <= ``amount_cents``. The difference is
    unapplied (customer credit). Each application's
    ``amount_cents + discount_cents + writeoff_cents`` must not exceed
    the target invoice's outstanding balance.
    """

    customer_id: int
    payment_date: date
    amount_cents: int = Field(..., gt=0)
    deposit_account_id: int
    method: Optional[str] = None
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    applications: list[PaymentApplicationCreate] = Field(default_factory=list)

    @field_validator("method")
    @classmethod
    def _method_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in _ALLOWED_METHODS:
            allowed = ", ".join(_ALLOWED_METHODS)
            raise ValueError(f"method must be one of: {allowed}")
        return v


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    payment_date: date
    amount_cents: int
    deposit_account_id: int
    method: Optional[str]
    reference: Optional[str]
    memo: Optional[str]
    journal_entry_id: int
    status: str
    applied_cents: int
    unapplied_cents: int
    applications: list[PaymentApplicationRead]

    @classmethod
    def from_orm_payment(cls, p) -> PaymentRead:
        return cls(
            id=p.id,
            customer_id=p.customer_id,
            payment_date=p.payment_date,
            amount_cents=p.amount_cents,
            deposit_account_id=p.deposit_account_id,
            method=p.method,
            reference=p.reference,
            memo=p.memo,
            journal_entry_id=p.journal_entry_id,
            status=p.status,
            applied_cents=p.applied_cents,
            unapplied_cents=p.unapplied_cents,
            applications=[
                PaymentApplicationRead.model_validate(a) for a in p.applications
            ],
        )
