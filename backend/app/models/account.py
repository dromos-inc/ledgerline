"""Chart-of-accounts model.

An account is a category in the ledger: Cash, Sales, Rent, etc. Every
journal line targets exactly one account. Accounts have a normal
balance (debit or credit) determined by their type.

Design notes:
- Accounts are never hard-deleted. Once a posted JE references an
  account, the account stays in the DB. Deactivation hides it from
  UIs without breaking history.
- Parent/child hierarchy is supported for display (sub-accounts roll
  up in reports) but not enforced at the DB layer beyond the FK.
"""

from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CompanyBase


class AccountType(str, enum.Enum):
    """The five fundamental account types."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class NormalBalance(str, enum.Enum):
    """Which side increases an account's balance."""

    DEBIT = "debit"
    CREDIT = "credit"


# Mapping from account type to its normal balance side.
NORMAL_BALANCE: dict[AccountType, NormalBalance] = {
    AccountType.ASSET: NormalBalance.DEBIT,
    AccountType.EXPENSE: NormalBalance.DEBIT,
    AccountType.LIABILITY: NormalBalance.CREDIT,
    AccountType.EQUITY: NormalBalance.CREDIT,
    AccountType.INCOME: NormalBalance.CREDIT,
}


def normal_balance(account_type: AccountType) -> NormalBalance:
    """Return the normal balance side for a given account type."""
    return NORMAL_BALANCE[account_type]


class Account(CompanyBase):
    """A single line in the chart of accounts."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_accounts_code"),
        CheckConstraint(
            "type IN ('asset','liability','equity','income','expense')",
            name="ck_accounts_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Short numeric/alphanumeric identifier (e.g. '1000', '4000-01').",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[AccountType] = mapped_column(
        SAEnum(
            AccountType,
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    subtype: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc=(
            "Reserved control-account marker: 'ar_control', 'ap_control', "
            "or 'sales_tax_default'. NULL for ordinary accounts. A partial "
            "unique index in migration 0002 guarantees at most one account "
            "carries each role. Used by triggers that block direct manual "
            "posting to control accounts."
        ),
    )

    parent: Mapped[Optional[Account]] = relationship(
        "Account",
        remote_side="Account.id",
        back_populates="children",
    )
    children: Mapped[list[Account]] = relationship(
        "Account",
        back_populates="parent",
        cascade="save-update, merge",
    )

    def normal_balance(self) -> NormalBalance:
        return normal_balance(self.type)

    def __repr__(self) -> str:
        return f"Account(id={self.id}, code={self.code!r}, name={self.name!r})"
