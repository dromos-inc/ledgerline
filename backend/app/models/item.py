"""Item catalog model.

An item is a product or service you sell. Invoice and bill lines can
either reference an item (which populates defaults for account, unit
price, and tax code) or be entirely freeform.

Phase 2 / S1 creates the table and the ORM class because
``invoice_lines.item_id`` is a FK to it. The service layer, API, and
UI for item CRUD ship in S3 (the Items+tax slice).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import CompanyBase


class Item(CompanyBase):
    """A catalog entry: service, product, or bundle."""

    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("code", name="uq_items_code"),
        CheckConstraint(
            "type IN ('service','product','bundle')",
            name="ck_items_type_valid",
        ),
        CheckConstraint(
            "unit_price_cents IS NULL OR unit_price_cents >= 0",
            name="ck_items_price_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="One of: service, product, bundle.",
    )
    default_income_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    default_expense_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    default_tax_code_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    unit_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="Display label for the quantity unit, e.g. 'hour', 'each', 'day'.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"Item(id={self.id}, code={self.code!r}, type={self.type})"
