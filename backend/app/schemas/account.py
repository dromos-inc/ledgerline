"""Chart-of-accounts request/response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.account import AccountType, NormalBalance


class AccountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    type: AccountType
    subtype: Optional[str] = Field(default=None, max_length=64)
    parent_id: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=512)


class AccountUpdate(BaseModel):
    """Editable fields: name, subtype, description. Type and code are frozen
    once any line references the account."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    subtype: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=512)


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: AccountType
    subtype: Optional[str]
    parent_id: Optional[int]
    is_active: bool
    description: Optional[str]
    normal_balance: NormalBalance

    @classmethod
    def from_orm_with_balance(cls, obj) -> AccountRead:
        return cls(
            id=obj.id,
            code=obj.code,
            name=obj.name,
            type=obj.type,
            subtype=obj.subtype,
            parent_id=obj.parent_id,
            is_active=obj.is_active,
            description=obj.description,
            normal_balance=obj.normal_balance(),
        )
