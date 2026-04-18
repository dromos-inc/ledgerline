"""/companies endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import get_registry_session
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.services import company as service

router = APIRouter(prefix="/companies", tags=["companies"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


@router.get("", response_model=list[CompanyRead])
def list_companies(session: Session = Depends(get_registry_session)) -> list[CompanyRead]:
    companies = service.list_companies(session)
    return [CompanyRead.model_validate(c) for c in companies]


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    payload: CompanyCreate,
    request: Request,
    session: Session = Depends(get_registry_session),
) -> CompanyRead:
    company = service.create_company(session, payload, _settings(request))
    return CompanyRead.model_validate(company)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: str,
    session: Session = Depends(get_registry_session),
) -> CompanyRead:
    return CompanyRead.model_validate(service.get_company(session, company_id))


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    session: Session = Depends(get_registry_session),
) -> CompanyRead:
    company = service.update_company(session, company_id, payload)
    return CompanyRead.model_validate(company)
