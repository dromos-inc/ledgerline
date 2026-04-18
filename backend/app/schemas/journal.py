"""Journal-entry request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.journal import JournalSource, JournalStatus


class JournalLineCreate(BaseModel):
    account_id: int
    debit_cents: int = Field(default=0, ge=0)
    credit_cents: int = Field(default=0, ge=0)
    memo: Optional[str] = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _exactly_one_side(self) -> JournalLineCreate:
        if (self.debit_cents > 0) == (self.credit_cents > 0):
            raise ValueError(
                "each line must have exactly one of debit_cents or credit_cents > 0"
            )
        return self


class JournalEntryCreate(BaseModel):
    entry_date: date
    posting_date: Optional[date] = None
    reference: Optional[str] = Field(default=None, max_length=64)
    memo: Optional[str] = Field(default=None, max_length=1024)
    lines: list[JournalLineCreate] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _balanced(self) -> JournalEntryCreate:
        debits = sum(line.debit_cents for line in self.lines)
        credits = sum(line.credit_cents for line in self.lines)
        if debits != credits:
            raise ValueError(
                f"entry does not balance: debits={debits} credits={credits}"
            )
        if self.posting_date is None:
            self.posting_date = self.entry_date
        return self


class JournalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_number: int
    account_id: int
    debit_cents: int
    credit_cents: int
    memo: Optional[str]


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    posting_date: date
    reference: Optional[str]
    memo: Optional[str]
    source_type: JournalSource
    source_id: Optional[int]
    status: JournalStatus
    created_by: Optional[str]
    reversal_of_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    lines: list[JournalLineRead]


class JournalEntryList(BaseModel):
    entries: list[JournalEntryRead]
    total: int
