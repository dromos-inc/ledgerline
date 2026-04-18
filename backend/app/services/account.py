"""Account services: CRUD on the chart of accounts for a single company."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit import AuditAction
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.audit import record_audit


def list_accounts(session: Session, *, include_inactive: bool = False) -> list[Account]:
    stmt = select(Account).order_by(Account.code)
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def get_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"account {account_id} not found",
        )
    return account


def create_account(
    session: Session,
    payload: AccountCreate,
    *,
    actor: str | None = None,
) -> Account:
    if payload.parent_id is not None:
        parent = session.get(Account, payload.parent_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"parent_id {payload.parent_id} not found",
            )
        if parent.type != payload.type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sub-account type must match parent type",
            )

    account = Account(**payload.model_dump())
    session.add(account)
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"account code {payload.code!r} already exists",
        ) from e

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="account",
        entity_id=account.id,
        after=payload.model_dump(),
        actor=actor,
    )
    return account


def update_account(
    session: Session,
    account_id: int,
    payload: AccountUpdate,
    *,
    actor: str | None = None,
) -> Account:
    account = get_account(session, account_id)
    before = {
        "name": account.name,
        "subtype": account.subtype,
        "description": account.description,
    }
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(account, key, value)
    session.flush()
    record_audit(
        session,
        action=AuditAction.UPDATE,
        entity_type="account",
        entity_id=account.id,
        before=before,
        after=updates,
        actor=actor,
    )
    return account


def deactivate_account(
    session: Session, account_id: int, *, actor: str | None = None
) -> Account:
    account = get_account(session, account_id)
    if not account.is_active:
        return account
    account.is_active = False
    session.flush()
    record_audit(
        session,
        action=AuditAction.DEACTIVATE,
        entity_type="account",
        entity_id=account.id,
        actor=actor,
    )
    return account


def reactivate_account(
    session: Session, account_id: int, *, actor: str | None = None
) -> Account:
    account = get_account(session, account_id)
    if account.is_active:
        return account
    account.is_active = True
    session.flush()
    record_audit(
        session,
        action=AuditAction.REACTIVATE,
        entity_type="account",
        entity_id=account.id,
        actor=actor,
    )
    return account
