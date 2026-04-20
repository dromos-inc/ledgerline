"""Vendor services: CRUD on the AP sub-ledger contacts.

Mirror of ``app.services.customer``. The shape is intentionally
identical so the AR/AP sides present a symmetric operator experience.
Differences:

- ``default_expense_account_id`` must reference an EXPENSE account
  (customers use INCOME). Real-world: a vendor who sells us capex can
  be served by setting the default account manually on each bill line,
  but the per-vendor default we surface stays narrow (expense).
- Hard delete is refused. Once migration 0004 lands the
  ``trg_vendors_no_delete_with_bills`` trigger enforces this at the
  DB layer; the service layer keeps it quiet by not exposing a
  DELETE route.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit import AuditAction
from app.models.contact import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate
from app.services.audit import record_audit


def _validate_account_for_expense(session: Session, account_id: int) -> None:
    """Default-expense account must exist and be of type 'expense'."""
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"default_expense_account_id {account_id} not found",
        )
    if account.type.value != "expense":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"default_expense_account_id {account_id} must be an expense "
                f"account, got {account.type.value!r}"
            ),
        )


def list_vendors(
    session: Session,
    *,
    include_inactive: bool = False,
    query: str | None = None,
) -> list[Vendor]:
    stmt = select(Vendor).order_by(Vendor.name)
    if not include_inactive:
        stmt = stmt.where(Vendor.is_active.is_(True))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Vendor.name.ilike(like),
                Vendor.code.ilike(like),
                Vendor.company.ilike(like),
                Vendor.email.ilike(like),
            )
        )
    return list(session.execute(stmt).scalars().all())


def get_vendor(session: Session, vendor_id: int) -> Vendor:
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"vendor {vendor_id} not found",
        )
    return vendor


def create_vendor(
    session: Session,
    payload: VendorCreate,
    *,
    actor: str | None = None,
) -> Vendor:
    if payload.default_expense_account_id is not None:
        _validate_account_for_expense(session, payload.default_expense_account_id)

    data = payload.model_dump()
    vendor = Vendor(**data)
    session.add(vendor)
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"vendor code {payload.code!r} already exists",
        ) from e

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="vendor",
        entity_id=vendor.id,
        after=data,
        actor=actor,
    )
    return vendor


def update_vendor(
    session: Session,
    vendor_id: int,
    payload: VendorUpdate,
    *,
    actor: str | None = None,
) -> Vendor:
    vendor = get_vendor(session, vendor_id)
    updates = payload.model_dump(exclude_unset=True)

    if (
        "default_expense_account_id" in updates
        and updates["default_expense_account_id"] is not None
    ):
        _validate_account_for_expense(session, updates["default_expense_account_id"])

    before = {key: getattr(vendor, key) for key in updates}
    for key, value in updates.items():
        setattr(vendor, key, value)
    session.flush()
    record_audit(
        session,
        action=AuditAction.UPDATE,
        entity_type="vendor",
        entity_id=vendor.id,
        before=before,
        after=updates,
        actor=actor,
    )
    return vendor


def deactivate_vendor(
    session: Session,
    vendor_id: int,
    *,
    actor: str | None = None,
) -> Vendor:
    vendor = get_vendor(session, vendor_id)
    if not vendor.is_active:
        return vendor
    vendor.is_active = False
    session.flush()
    record_audit(
        session,
        action=AuditAction.DEACTIVATE,
        entity_type="vendor",
        entity_id=vendor.id,
        actor=actor,
    )
    return vendor


def reactivate_vendor(
    session: Session,
    vendor_id: int,
    *,
    actor: str | None = None,
) -> Vendor:
    vendor = get_vendor(session, vendor_id)
    if vendor.is_active:
        return vendor
    vendor.is_active = True
    session.flush()
    record_audit(
        session,
        action=AuditAction.REACTIVATE,
        entity_type="vendor",
        entity_id=vendor.id,
        actor=actor,
    )
    return vendor