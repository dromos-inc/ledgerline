"""Audit-log helper.

Call ``record_audit`` from services when something interesting happens.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditLog


def record_audit(
    session: Session,
    *,
    action: AuditAction | str,
    entity_type: str,
    entity_id: str | int,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    actor: Optional[str] = None,
    note: Optional[str] = None,
) -> AuditLog:
    """Append a single audit row. Returns the persisted row (with id)."""
    action_value = action.value if isinstance(action, AuditAction) else action
    row = AuditLog(
        actor=actor,
        action=action_value,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before_json=json.dumps(before, default=str) if before is not None else None,
        after_json=json.dumps(after, default=str) if after is not None else None,
        note=note,
    )
    session.add(row)
    session.flush()
    return row
