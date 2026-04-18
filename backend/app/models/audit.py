"""Append-only audit log.

Every write that matters — creating, posting, voiding, editing — is
recorded here with before/after JSON snapshots. The table is
append-only: writes never UPDATE or DELETE existing rows.
"""

from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import CompanyBase


class AuditAction(str, enum.Enum):
    """Standard audit actions. Free-form strings are tolerated (the DB
    column is a ``String(64)``), but using the enum is preferred."""

    CREATE = "create"
    UPDATE = "update"
    POST = "post"
    VOID = "void"
    DELETE = "delete"
    DEACTIVATE = "deactivate"
    REACTIVATE = "reactivate"


class AuditLog(CompanyBase):
    """One row per auditable event."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="User identifier. None for system actions.",
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Stringified primary key of the affected entity.",
    )
    before_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        return (
            f"AuditLog(id={self.id}, action={self.action}, "
            f"{self.entity_type}:{self.entity_id})"
        )
