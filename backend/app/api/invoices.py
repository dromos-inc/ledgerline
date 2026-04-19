"""/companies/{company_id}/invoices endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.invoice import InvoiceCreate, InvoiceRead, InvoiceUpdate
from app.services import invoice as service

router = APIRouter(
    prefix="/companies/{company_id}/invoices",
    tags=["invoices"],
)


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    customer_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_company_session),
) -> list[InvoiceRead]:
    invoices, _total = service.list_invoices(
        session,
        customer_id=customer_id,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [InvoiceRead.from_orm_invoice(inv) for inv in invoices]


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    session: Session = Depends(get_company_session),
) -> InvoiceRead:
    invoice = service.create_draft(session, payload)
    return InvoiceRead.from_orm_invoice(invoice)


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    session: Session = Depends(get_company_session),
) -> InvoiceRead:
    return InvoiceRead.from_orm_invoice(service.get_invoice(session, invoice_id))


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    session: Session = Depends(get_company_session),
) -> InvoiceRead:
    invoice = service.update_draft(session, invoice_id, payload)
    return InvoiceRead.from_orm_invoice(invoice)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: int,
    session: Session = Depends(get_company_session),
) -> None:
    service.delete_draft(session, invoice_id)


@router.post("/{invoice_id}/post", response_model=InvoiceRead)
def post_invoice(
    invoice_id: int,
    session: Session = Depends(get_company_session),
) -> InvoiceRead:
    invoice = service.post_invoice(session, invoice_id)
    return InvoiceRead.from_orm_invoice(invoice)


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(
    invoice_id: int,
    session: Session = Depends(get_company_session),
) -> InvoiceRead:
    invoice = service.void_invoice(session, invoice_id)
    return InvoiceRead.from_orm_invoice(invoice)
