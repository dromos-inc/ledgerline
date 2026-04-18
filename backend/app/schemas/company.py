"""Company request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.registry import EntityType, TaxBasis, is_valid_company_id


class CompanyCreate(BaseModel):
    """Payload to create a new company."""

    id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="URL-safe slug. Also the filename of the company DB.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    entity_type: EntityType = EntityType.SCHEDULE_C
    tax_basis: TaxBasis = TaxBasis.CASH
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    fiscal_year_start: str = Field(
        default="01-01",
        pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$",
        description="Month-day as MM-DD.",
    )

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not is_valid_company_id(v):
            raise ValueError(
                "id must be lowercase alphanumeric (plus - and _), "
                "max 63 chars, starting with a letter or digit"
            )
        return v


class CompanyUpdate(BaseModel):
    """Partial update. All fields optional; only provided ones change."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    entity_type: Optional[EntityType] = None
    tax_basis: Optional[TaxBasis] = None
    fiscal_year_start: Optional[str] = Field(
        default=None,
        pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$",
    )


class CompanyRead(BaseModel):
    """Company row as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    entity_type: EntityType
    tax_basis: TaxBasis
    base_currency: str
    fiscal_year_start: str
    created_at: datetime
    updated_at: datetime
