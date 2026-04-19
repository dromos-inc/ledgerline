"""/companies/{company_id}/customers endpoints.

CRUD for AR sub-ledger contacts. Mirrors the accounts router so the
API surface is consistent.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services import customer as service

router = APIRouter(
    prefix="/companies/{company_id}/customers",
    tags=["customers"],
)


@router.get("", response_model=list[CustomerRead])
def list_customers(
    include_inactive: bool = Query(default=False),
    q: Optional[str] = Query(default=None, description="Search name, code, company, email."),
    session: Session = Depends(get_company_session),
) -> list[CustomerRead]:
    customers = service.list_customers(
        session, include_inactive=include_inactive, query=q
    )
    return [CustomerRead.model_validate(c) for c in customers]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    session: Session = Depends(get_company_session),
) -> CustomerRead:
    customer = service.create_customer(session, payload)
    return CustomerRead.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    session: Session = Depends(get_company_session),
) -> CustomerRead:
    return CustomerRead.model_validate(service.get_customer(session, customer_id))


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    session: Session = Depends(get_company_session),
) -> CustomerRead:
    customer = service.update_customer(session, customer_id, payload)
    return CustomerRead.model_validate(customer)


@router.post("/{customer_id}/deactivate", response_model=CustomerRead)
def deactivate_customer(
    customer_id: int,
    session: Session = Depends(get_company_session),
) -> CustomerRead:
    customer = service.deactivate_customer(session, customer_id)
    return CustomerRead.model_validate(customer)


@router.post("/{customer_id}/reactivate", response_model=CustomerRead)
def reactivate_customer(
    customer_id: int,
    session: Session = Depends(get_company_session),
) -> CustomerRead:
    customer = service.reactivate_customer(session, customer_id)
    return CustomerRead.model_validate(customer)
