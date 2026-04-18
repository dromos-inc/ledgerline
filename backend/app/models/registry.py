"""Registry-database models: companies and global settings."""

from __future__ import annotations

import enum
import re
from datetime import date

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import RegistryBase

# Slug validation: URL-safe lowercase identifier. Keeps on-disk filenames
# tidy and disqualifies anything that could try to traverse the filesystem.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def is_valid_company_id(value: str) -> bool:
    """True if ``value`` is a safe company id (slug)."""
    return bool(_SLUG_RE.fullmatch(value))


class EntityType(str, enum.Enum):
    """Supported legal entity types for MVP (PRD §15 Q5)."""

    SCHEDULE_C = "schedule_c"
    S_CORP = "s_corp"


class TaxBasis(str, enum.Enum):
    """Official tax filing basis. Reports can be run on either basis
    regardless of this setting (PRD §15 Q4)."""

    CASH = "cash"
    ACCRUAL = "accrual"


class Company(RegistryBase):
    """A company book. The id is also the filename stem of its DB file.

    Example: ``Company(id="dromos-inc", name="Dromos Inc.")`` lives at
    ``<data_dir>/companies/dromos-inc.db``.
    """

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(
            EntityType,
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EntityType.SCHEDULE_C,
    )
    tax_basis: Mapped[TaxBasis] = mapped_column(
        SAEnum(
            TaxBasis,
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TaxBasis.CASH,
    )
    base_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        doc="ISO 4217 code. USD only for MVP; multi-currency deferred.",
    )
    # Fiscal year start as month-day, stored as a string "MM-DD". January 1
    # is the default.
    fiscal_year_start: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="01-01",
    )

    def fiscal_year_start_date(self, year: int) -> date:
        """Return the fiscal year start date for a given calendar year."""
        month_str, day_str = self.fiscal_year_start.split("-")
        return date(year, int(month_str), int(day_str))

    def __repr__(self) -> str:
        return f"Company(id={self.id!r}, name={self.name!r})"
