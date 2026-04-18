"""JSON import endpoint.

Restores a company from a ``dump_company`` payload. Lives outside the
per-company URL tree because at import time the company doesn't exist yet.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Query, Request, status

from app.config import Settings
from app.schemas.company import CompanyRead
from app.services.import_export import import_company

router = APIRouter(prefix="/import", tags=["import"])


@router.post(
    "/company",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def import_company_json(
    request: Request,
    payload: dict[str, Any] = Body(
        ..., description="A JSON document produced by GET /export/company.json."
    ),
    override_id: Optional[str] = Query(
        default=None,
        description="Import under a different company id (avoids collision).",
    ),
) -> CompanyRead:
    settings: Settings = request.app.state.settings
    company = import_company(settings, payload, override_id=override_id)
    return CompanyRead.model_validate(company)
