"""Vendor request/response schemas.

Mirror of ``app.schemas.customer``. Differences from the customer side:

- ``default_expense_account_id`` (instead of income).
- ``is_1099`` boolean flag (vendors may need 1099 reporting; the export
  lands in Phase 4 but the data captures now).
- No ``shipping_address`` (bills have no shipment direction).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_TERMS = ("net_15", "net_30", "net_60", "due_on_receipt", "custom")


def _validate_terms(value: str) -> str:
    if value not in _ALLOWED_TERMS:
        allowed = ", ".join(_ALLOWED_TERMS)
        raise ValueError(f"default_terms must be one of: {allowed}")
    return value


def _validate_email(value: Optional[str]) -> Optional[str]:
    """Minimal email sanity check. Same as the customer-side helper."""
    if value is None:
        return value
    value = value.strip()
    if not value:
        return None
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("email must contain a local part and domain separated by '@'")
    return value


class VendorBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=64)
    tax_id: Optional[str] = Field(default=None, max_length=64)
    billing_address: Optional[str] = Field(default=None, max_length=512)
    default_terms: str = Field(default="net_30", max_length=32)
    default_expense_account_id: Optional[int] = None
    is_1099: bool = False
    notes: Optional[str] = None

    @field_validator("default_terms")
    @classmethod
    def _terms_must_be_allowed(cls, v: str) -> str:
        return _validate_terms(v)

    @field_validator("email")
    @classmethod
    def _email_format(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    """All fields optional. Only provided fields are updated."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=64)
    tax_id: Optional[str] = Field(default=None, max_length=64)
    billing_address: Optional[str] = Field(default=None, max_length=512)
    default_terms: Optional[str] = Field(default=None, max_length=32)
    default_expense_account_id: Optional[int] = None
    is_1099: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("default_terms")
    @classmethod
    def _terms_must_be_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_terms(v)

    @field_validator("email")
    @classmethod
    def _email_format(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    company: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    tax_id: Optional[str]
    billing_address: Optional[str]
    default_terms: str
    default_expense_account_id: Optional[int]
    is_active: bool
    is_1099: bool
    notes: Optional[str]
