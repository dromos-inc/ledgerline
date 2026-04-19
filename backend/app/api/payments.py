"""/companies/{company_id}/payments endpoints.

Create-with-applications + void. Individual application add/remove is
deferred behind void+recreate per the service design (see
``app/services/payment.py`` module docstring).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services import payment as service

router = APIRouter(
    prefix="/companies/{company_id}/payments",
    tags=["payments"],
)


@router.get("", response_model=list[PaymentRead])
def list_payments(
    customer_id: Optional[int] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_company_session),
) -> list[PaymentRead]:
    payments, _total = service.list_payments(
        session,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [PaymentRead.from_orm_payment(p) for p in payments]


@router.post("", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    session: Session = Depends(get_company_session),
) -> PaymentRead:
    payment = service.create_payment(session, payload)
    return PaymentRead.from_orm_payment(payment)


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: int,
    session: Session = Depends(get_company_session),
) -> PaymentRead:
    return PaymentRead.from_orm_payment(service.get_payment(session, payment_id))


@router.post("/{payment_id}/void", response_model=PaymentRead)
def void_payment(
    payment_id: int,
    session: Session = Depends(get_company_session),
) -> PaymentRead:
    payment = service.void_payment(session, payment_id)
    return PaymentRead.from_orm_payment(payment)
