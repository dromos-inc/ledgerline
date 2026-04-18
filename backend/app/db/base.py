"""SQLAlchemy declarative bases.

Two separate declarative bases live here so that model classes cannot
accidentally be registered against the wrong metadata. Registry tables
(companies, global settings) extend ``RegistryBase``; per-company
tables (accounts, journal_entries, etc.) extend ``CompanyBase``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime``.

    SQLite does not natively carry tz info. We store UTC ISO-8601 strings
    and round-trip them as aware datetimes via SQLAlchemy's ``DateTime``
    with ``timezone=True``.
    """
    return datetime.now(timezone.utc)


class _TimestampMixin:
    """Shared ``created_at`` and ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.current_timestamp(),
    )


class RegistryBase(_TimestampMixin, DeclarativeBase):
    """Declarative base for the registry database."""

    type_annotation_map: ClassVar[dict[type, Any]] = {}


class CompanyBase(_TimestampMixin, DeclarativeBase):
    """Declarative base for per-company databases."""

    type_annotation_map: ClassVar[dict[type, Any]] = {}


# Keep a single alias so external code can ``from app.db import Base`` without
# having to know the distinction when context makes it obvious.
Base = CompanyBase
