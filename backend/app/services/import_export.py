"""Import a JSON export into a new company.

Account ids from the source are preserved (we set them explicitly on INSERT)
so journal lines keep their original account references. Journal entries and
their lines are likewise inserted with their original ids, keeping audit
trails intact.

A voided/posted entry cannot have its lines inserted post-facto (the
``trg_journal_lines_no_insert_on_posted`` trigger would reject them), so the
import temporarily stages every entry as DRAFT, attaches its lines, flushes,
then flips the status to its archived value. The triggers allow one
draft → posted transition and one posted → void transition, which matches
what a normal workflow would do.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.engines import company_engine
from app.db.schema import ensure_company_schema
from app.db.session import company_session, registry_session
from app.export.json_dump import EXPORT_VERSION
from app.models.account import Account, AccountType
from app.models.journal import JournalEntry, JournalLine, JournalSource, JournalStatus
from app.models.registry import Company, EntityType, TaxBasis, is_valid_company_id


def import_company(
    settings: Settings,
    payload: dict[str, Any],
    *,
    override_id: str | None = None,
) -> Company:
    """Restore a company from a JSON payload produced by ``dump_company``.

    If ``override_id`` is provided, the imported company uses that id
    instead of the one in the payload. Useful when restoring a backup to
    a new name without colliding with an existing one.
    """
    version = payload.get("ledgerline_export_version")
    if version != EXPORT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"unsupported export version: got {version!r}, expected {EXPORT_VERSION}"
            ),
        )

    company_payload = payload["company"]
    target_id = override_id or company_payload["id"]
    if not is_valid_company_id(target_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid company id {target_id!r}",
        )

    # 1. Create the company row in the registry (if not existing).
    with registry_session(settings) as reg_sess:
        existing = reg_sess.get(Company, target_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"company {target_id!r} already exists",
            )
        company = Company(
            id=target_id,
            name=company_payload["name"],
            entity_type=EntityType(company_payload.get("entity_type", "schedule_c")),
            tax_basis=TaxBasis(company_payload.get("tax_basis", "cash")),
            base_currency=company_payload.get("base_currency", "USD"),
            fiscal_year_start=company_payload.get("fiscal_year_start", "01-01"),
        )
        reg_sess.add(company)

    # 2. Provision the DB file and schema.
    engine = company_engine(settings, target_id)
    ensure_company_schema(engine)

    # 3. Insert accounts and journal entries + lines inside the company DB.
    with company_session(target_id, settings) as co_sess:
        _restore_accounts(co_sess, payload["accounts"])
        _restore_entries(co_sess, payload["journal_entries"])

    # 4. Return the fresh company row.
    with registry_session(settings) as reg_sess:
        return reg_sess.get(Company, target_id)  # type: ignore[return-value]


def _restore_accounts(session: Session, accounts: list[dict[str, Any]]) -> None:
    """Re-insert accounts, preserving their ids."""
    for a in accounts:
        account = Account(
            id=a["id"],
            code=a["code"],
            name=a["name"],
            type=AccountType(a["type"]),
            subtype=a.get("subtype"),
            parent_id=a.get("parent_id"),
            is_active=a.get("is_active", True),
            description=a.get("description"),
        )
        session.add(account)
    session.flush()


def _restore_entries(session: Session, entries: list[dict[str, Any]]) -> None:
    """Re-insert journal entries and their lines.

    Entries are created as DRAFT, have their lines attached, then
    transitioned to their archived status so the insert-on-posted trigger
    doesn't fire on the line inserts.
    """
    for e in entries:
        final_status = JournalStatus(e["status"])
        entry = JournalEntry(
            id=e["id"],
            entry_date=_parse_date(e["entry_date"]),
            posting_date=_parse_date(e["posting_date"]),
            reference=e.get("reference"),
            memo=e.get("memo"),
            source_type=JournalSource(e.get("source_type", "manual")),
            source_id=e.get("source_id"),
            status=JournalStatus.DRAFT,
            created_by=e.get("created_by"),
            reversal_of_id=e.get("reversal_of_id"),
        )
        entry.lines = [
            JournalLine(
                line_number=line["line_number"],
                account_id=line["account_id"],
                debit_cents=line["debit_cents"],
                credit_cents=line["credit_cents"],
                memo=line.get("memo"),
            )
            for line in e["lines"]
        ]
        session.add(entry)
        session.flush()
        # Transition: draft -> posted -> void (if needed). Each hop is
        # permitted by the triggers.
        if final_status in (JournalStatus.POSTED, JournalStatus.VOID):
            entry.status = JournalStatus.POSTED
            session.flush()
        if final_status == JournalStatus.VOID:
            entry.status = JournalStatus.VOID
            session.flush()


def _parse_date(value: str) -> _date:
    # ``date.fromisoformat`` accepts YYYY-MM-DD; datetimes get truncated.
    try:
        return _date.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(value).date()
