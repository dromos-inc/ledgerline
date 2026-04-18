"""JSON full-company export and import.

The JSON document is intended as a round-trip-safe backup: export a company
from one Ledgerline instance, import it into another, and the ledger is
byte-identical. The format is versioned so older exports remain importable
after schema changes.

Shape (v1):

.. code-block:: json

    {
      "ledgerline_export_version": 1,
      "exported_at": "2026-04-18T19:00:00Z",
      "company": {...},
      "accounts": [...],
      "journal_entries": [
        {
          "id": 1, "entry_date": "...", ...,
          "lines": [{...}, {...}]
        }
      ],
      "audit_log": [...]
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.account import Account
from app.models.audit import AuditLog
from app.models.journal import JournalEntry, JournalLine
from app.models.registry import Company

EXPORT_VERSION = 1


def dump_company(
    registry_session: Session,
    company_session: Session,
    company_id: str,
) -> dict[str, Any]:
    """Build a complete JSON-serializable dump of a company."""
    company = registry_session.get(Company, company_id)
    if company is None:
        raise ValueError(f"company {company_id!r} not found")

    accounts = list(
        company_session.execute(select(Account).order_by(Account.code)).scalars().all()
    )
    entries = list(
        company_session.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .order_by(JournalEntry.id)
        )
        .scalars()
        .all()
    )
    audit_rows = list(
        company_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
    )

    return {
        "ledgerline_export_version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "company": _dump_company(company),
        "accounts": [_dump_account(a) for a in accounts],
        "journal_entries": [_dump_entry(e) for e in entries],
        "audit_log": [_dump_audit(r) for r in audit_rows],
    }


def _dump_company(c: Company) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "entity_type": c.entity_type.value,
        "tax_basis": c.tax_basis.value,
        "base_currency": c.base_currency,
        "fiscal_year_start": c.fiscal_year_start,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _dump_account(a: Account) -> dict[str, Any]:
    return {
        "id": a.id,
        "code": a.code,
        "name": a.name,
        "type": a.type.value,
        "subtype": a.subtype,
        "parent_id": a.parent_id,
        "is_active": a.is_active,
        "description": a.description,
    }


def _dump_entry(e: JournalEntry) -> dict[str, Any]:
    return {
        "id": e.id,
        "entry_date": e.entry_date.isoformat(),
        "posting_date": e.posting_date.isoformat(),
        "reference": e.reference,
        "memo": e.memo,
        "source_type": e.source_type.value,
        "source_id": e.source_id,
        "status": e.status.value,
        "created_by": e.created_by,
        "reversal_of_id": e.reversal_of_id,
        "lines": [_dump_line(line) for line in e.lines],
    }


def _dump_line(line: JournalLine) -> dict[str, Any]:
    return {
        "line_number": line.line_number,
        "account_id": line.account_id,
        "debit_cents": line.debit_cents,
        "credit_cents": line.credit_cents,
        "memo": line.memo,
    }


def _dump_audit(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "actor": row.actor,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "before_json": row.before_json,
        "after_json": row.after_json,
        "note": row.note,
        "created_at": row.created_at.isoformat(),
    }
