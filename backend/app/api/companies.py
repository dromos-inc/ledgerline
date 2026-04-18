"""/companies endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import get_registry_session
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.seed import TEMPLATES
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
    template: Optional[str] = Query(
        default=None,
        description=(
            "Optional: key of a chart-of-accounts template to seed (e.g. "
            "'sched_c_service', 'sched_c_retail', 's_corp_general'). "
            "See GET /templates."
        ),
    ),
    session: Session = Depends(get_registry_session),
) -> CompanyRead:
    if template is not None and template not in TEMPLATES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"unknown template {template!r}; "
                f"available: {sorted(TEMPLATES)}"
            ),
        )
    company = service.create_company(
        session, payload, _settings(request), template=template
    )
    return CompanyRead.model_validate(company)


@router.get("/templates", tags=["templates"])
def list_templates() -> list[dict]:
    """List available chart-of-accounts templates."""
    return [
        {
            "key": t.key,
            "label": t.label,
            "description": t.description,
            "account_count": len(t.accounts),
        }
        for t in TEMPLATES.values()
    ]


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
