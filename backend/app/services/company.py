"""Company services: create, list, get, update.

The registry DB stores company metadata. Each company also has its own
SQLite file, which is provisioned on the first create.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.engines import company_engine
from app.db.schema import ensure_company_schema
from app.db.session import company_session
from app.models.registry import Company
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.seed import apply_template


def list_companies(session: Session) -> list[Company]:
    stmt = select(Company).order_by(Company.name)
    return list(session.execute(stmt).scalars().all())


def get_company(session: Session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"company {company_id!r} not found",
        )
    return company


def create_company(
    session: Session,
    payload: CompanyCreate,
    settings: Settings,
    *,
    template: str | None = None,
) -> Company:
    existing = session.get(Company, payload.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"company {payload.id!r} already exists",
        )
    company = Company(**payload.model_dump())
    session.add(company)
    session.flush()

    # Provision the company database file.
    engine = company_engine(settings, company.id)
    ensure_company_schema(engine)

    if template:
        with company_session(company.id, settings) as co_session:
            apply_template(co_session, template)

    return company


def update_company(
    session: Session, company_id: str, payload: CompanyUpdate
) -> Company:
    company = get_company(session, company_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(company, key, value)
    session.flush()
    return company


def delete_company(session: Session, company_id: str) -> None:
    """Mark a company as deleted. NOT in MVP; raises NotImplemented."""
    _ = session
    _ = company_id
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="company deletion is not supported; export and archive the file manually",
    )
