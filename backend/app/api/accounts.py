"""/companies/{company_id}/accounts endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.services import account as service

router = APIRouter(
    prefix="/companies/{company_id}/accounts",
    tags=["accounts"],
)


@router.get("", response_model=list[AccountRead])
def list_accounts(
    include_inactive: bool = Query(default=False),
    session: Session = Depends(get_company_session),
) -> list[AccountRead]:
    accounts = service.list_accounts(session, include_inactive=include_inactive)
    return [AccountRead.from_orm_with_balance(a) for a in accounts]


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    session: Session = Depends(get_company_session),
) -> AccountRead:
    account = service.create_account(session, payload)
    return AccountRead.from_orm_with_balance(account)


@router.get("/{account_id}", response_model=AccountRead)
def get_account(
    account_id: int,
    session: Session = Depends(get_company_session),
) -> AccountRead:
    return AccountRead.from_orm_with_balance(service.get_account(session, account_id))


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    session: Session = Depends(get_company_session),
) -> AccountRead:
    account = service.update_account(session, account_id, payload)
    return AccountRead.from_orm_with_balance(account)


@router.post("/{account_id}/deactivate", response_model=AccountRead)
def deactivate_account(
    account_id: int,
    session: Session = Depends(get_company_session),
) -> AccountRead:
    account = service.deactivate_account(session, account_id)
    return AccountRead.from_orm_with_balance(account)


@router.post("/{account_id}/reactivate", response_model=AccountRead)
def reactivate_account(
    account_id: int,
    session: Session = Depends(get_company_session),
) -> AccountRead:
    account = service.reactivate_account(session, account_id)
    return AccountRead.from_orm_with_balance(account)
