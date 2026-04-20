"""/companies/{company_id}/bills endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.bill import BillCreate, BillRead, BillUpdate
from app.services import bill as service

router = APIRouter(
    prefix="/companies/{company_id}/bills",
    tags=["bills"],
)


@router.get("", response_model=list[BillRead])
def list_bills(
    vendor_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_company_session),
) -> list[BillRead]:
    bills, _total = service.list_bills(
        session,
        vendor_id=vendor_id,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [BillRead.from_orm_bill(b) for b in bills]


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: BillCreate,
    session: Session = Depends(get_company_session),
) -> BillRead:
    bill = service.create_draft(session, payload)
    return BillRead.from_orm_bill(bill)


@router.get("/{bill_id}", response_model=BillRead)
def get_bill(
    bill_id: int,
    session: Session = Depends(get_company_session),
) -> BillRead:
    return BillRead.from_orm_bill(service.get_bill(session, bill_id))


@router.patch("/{bill_id}", response_model=BillRead)
def update_bill(
    bill_id: int,
    payload: BillUpdate,
    session: Session = Depends(get_company_session),
) -> BillRead:
    bill = service.update_draft(session, bill_id, payload)
    return BillRead.from_orm_bill(bill)


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(
    bill_id: int,
    session: Session = Depends(get_company_session),
) -> None:
    service.delete_draft(session, bill_id)


@router.post("/{bill_id}/post", response_model=BillRead)
def post_bill(
    bill_id: int,
    session: Session = Depends(get_company_session),
) -> BillRead:
    bill = service.post_bill(session, bill_id)
    return BillRead.from_orm_bill(bill)


@router.post("/{bill_id}/void", response_model=BillRead)
def void_bill(
    bill_id: int,
    session: Session = Depends(get_company_session),
) -> BillRead:
    bill = service.void_bill(session, bill_id)
    return BillRead.from_orm_bill(bill)