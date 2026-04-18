"""/companies/{company_id}/accounts/{account_id}/register endpoint."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.register import Register
from app.services import register as service

router = APIRouter(
    prefix="/companies/{company_id}/accounts/{account_id}",
    tags=["register"],
)


@router.get("/register", response_model=Register)
def get_register(
    account_id: int,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    session: Session = Depends(get_company_session),
) -> Register:
    return service.build_register(
        session, account_id, start_date=start_date, end_date=end_date
    )
