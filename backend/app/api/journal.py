"""/companies/{company_id}/journal-entries endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryList,
    JournalEntryRead,
)
from app.services import journal as service

router = APIRouter(
    prefix="/companies/{company_id}/journal-entries",
    tags=["journal-entries"],
)


@router.get("", response_model=JournalEntryList)
def list_entries(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_company_session),
) -> JournalEntryList:
    entries, total = service.list_entries(
        session,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return JournalEntryList(
        entries=[JournalEntryRead.model_validate(e) for e in entries],
        total=total,
    )


@router.post("", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: JournalEntryCreate,
    session: Session = Depends(get_company_session),
) -> JournalEntryRead:
    entry = service.create_entry(session, payload)
    return JournalEntryRead.model_validate(entry)


@router.get("/{entry_id}", response_model=JournalEntryRead)
def get_entry(
    entry_id: int,
    session: Session = Depends(get_company_session),
) -> JournalEntryRead:
    return JournalEntryRead.model_validate(service.get_entry(session, entry_id))


@router.post("/{entry_id}/post", response_model=JournalEntryRead)
def post_entry(
    entry_id: int,
    session: Session = Depends(get_company_session),
) -> JournalEntryRead:
    entry = service.post_entry(session, entry_id)
    return JournalEntryRead.model_validate(entry)


@router.post("/{entry_id}/void", response_model=JournalEntryRead)
def void_entry(
    entry_id: int,
    memo: Optional[str] = Body(default=None, embed=True),
    session: Session = Depends(get_company_session),
) -> JournalEntryRead:
    entry = service.void_entry(session, entry_id, memo=memo)
    return JournalEntryRead.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(
    entry_id: int,
    session: Session = Depends(get_company_session),
) -> Response:
    service.delete_draft(session, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
