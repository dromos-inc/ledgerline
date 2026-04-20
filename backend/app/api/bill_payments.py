"""/companies/{company_id}/bill-payments endpoints.

Create-with-applications + void. Mirror of the AR-side /payments router.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.bill_payment import BillPaymentCreate, BillPaymentRead
from app.services import bill_payment as service

router = APIRouter(
    prefix="/companies/{company_id}/bill-payments",
    tags=["bill_payments"],
)


@router.get("", response_model=list[BillPaymentRead])
def list_bill_payments(
    vendor_id: Optional[int] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_company_session),
) -> list[BillPaymentRead]:
    payments, _total = service.list_bill_payments(
        session,
        vendor_id=vendor_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [BillPaymentRead.from_orm_payment(p) for p in payments]


@router.post("", response_model=BillPaymentRead, status_code=status.HTTP_201_CREATED)
def create_bill_payment(
    payload: BillPaymentCreate,
    session: Session = Depends(get_company_session),
) -> BillPaymentRead:
    payment = service.create_bill_payment(session, payload)
    return BillPaymentRead.from_orm_payment(payment)


@router.get("/{payment_id}", response_model=BillPaymentRead)
def get_bill_payment(
    payment_id: int,
    session: Session = Depends(get_company_session),
) -> BillPaymentRead:
    return BillPaymentRead.from_orm_payment(
        service.get_bill_payment(session, payment_id)
    )


@router.post("/{payment_id}/void", response_model=BillPaymentRead)
def void_bill_payment(
    payment_id: int,
    session: Session = Depends(get_company_session),
) -> BillPaymentRead:
    payment = service.void_bill_payment(session, payment_id)
    return BillPaymentRead.from_orm_payment(payment)