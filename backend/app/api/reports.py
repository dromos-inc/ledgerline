"""/companies/{company_id}/reports endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.reports.basis import Basis
from app.reports.profit_loss import build_profit_loss
from app.reports.trial_balance import build_trial_balance
from app.schemas.reports import ProfitLossReport, TrialBalanceReport

router = APIRouter(
    prefix="/companies/{company_id}/reports",
    tags=["reports"],
)


@router.get("/trial-balance", response_model=TrialBalanceReport)
def trial_balance(
    as_of_date: date = Query(..., description="Inclusive as-of date."),
    basis: Basis = Query(default=Basis.ACCRUAL),
    include_zero: bool = Query(default=False),
    session: Session = Depends(get_company_session),
) -> TrialBalanceReport:
    return build_trial_balance(
        session, as_of_date=as_of_date, basis=basis, include_zero=include_zero
    )


@router.get("/profit-loss", response_model=ProfitLossReport)
def profit_loss(
    start_date: date = Query(..., description="Inclusive start date."),
    end_date: date = Query(..., description="Inclusive end date."),
    basis: Basis = Query(default=Basis.ACCRUAL),
    compare_prior_period: bool = Query(default=False),
    session: Session = Depends(get_company_session),
) -> ProfitLossReport:
    return build_profit_loss(
        session,
        start_date=start_date,
        end_date=end_date,
        basis=basis,
        compare_prior_period=compare_prior_period,
    )
