"""/companies/{company_id}/vendors endpoints.

CRUD for AP sub-ledger contacts. Mirrors the customers router so the
API surface is consistent across AR/AP.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.vendor import VendorCreate, VendorRead, VendorUpdate
from app.services import vendor as service

router = APIRouter(
    prefix="/companies/{company_id}/vendors",
    tags=["vendors"],
)


@router.get("", response_model=list[VendorRead])
def list_vendors(
    include_inactive: bool = Query(default=False),
    q: Optional[str] = Query(default=None, description="Search name, code, company, email."),
    session: Session = Depends(get_company_session),
) -> list[VendorRead]:
    vendors = service.list_vendors(session, include_inactive=include_inactive, query=q)
    return [VendorRead.model_validate(v) for v in vendors]


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    session: Session = Depends(get_company_session),
) -> VendorRead:
    vendor = service.create_vendor(session, payload)
    return VendorRead.model_validate(vendor)


@router.get("/{vendor_id}", response_model=VendorRead)
def get_vendor(
    vendor_id: int,
    session: Session = Depends(get_company_session),
) -> VendorRead:
    return VendorRead.model_validate(service.get_vendor(session, vendor_id))


@router.patch("/{vendor_id}", response_model=VendorRead)
def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    session: Session = Depends(get_company_session),
) -> VendorRead:
    vendor = service.update_vendor(session, vendor_id, payload)
    return VendorRead.model_validate(vendor)


@router.post("/{vendor_id}/deactivate", response_model=VendorRead)
def deactivate_vendor(
    vendor_id: int,
    session: Session = Depends(get_company_session),
) -> VendorRead:
    vendor = service.deactivate_vendor(session, vendor_id)
    return VendorRead.model_validate(vendor)


@router.post("/{vendor_id}/reactivate", response_model=VendorRead)
def reactivate_vendor(
    vendor_id: int,
    session: Session = Depends(get_company_session),
) -> VendorRead:
    vendor = service.reactivate_vendor(session, vendor_id)
    return VendorRead.model_validate(vendor)
