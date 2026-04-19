"""/companies/{company_id}/reports endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_company_session
from app.reports.ar_aging import build_ar_aging
from app.reports.balance_sheet import build_balance_sheet
from app.reports.basis import Basis
from app.reports.profit_loss import build_profit_loss
from app.reports.reconciliation import build_reconciliation
from app.reports.trial_balance import build_trial_balance
from app.schemas.reports import (
    BalanceSheetReport,
    ProfitLossReport,
    TrialBalanceReport,
)

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


@router.get("/balance-sheet", response_model=BalanceSheetReport)
def balance_sheet(
    as_of_date: date = Query(..., description="Inclusive as-of date."),
    basis: Basis = Query(default=Basis.ACCRUAL),
    session: Session = Depends(get_company_session),
) -> BalanceSheetReport:
    return build_balance_sheet(session, as_of_date=as_of_date, basis=basis)


@router.get("/ar-aging")
def ar_aging(
    as_of_date: date = Query(..., description="Inclusive as-of date."),
    include_zero_balance: bool = Query(default=False),
    session: Session = Depends(get_company_session),
) -> dict[str, Any]:
    """AR aging buckets by customer.

    Buckets: current (not yet due), 1-30, 31-60, 61-90, 90+ days
    overdue. Voided and paid invoices are excluded; draft invoices
    don't count either (no JE has fired).
    """
    report = build_ar_aging(
        session, as_of_date=as_of_date, include_zero_balance=include_zero_balance
    )
    return {
        "as_of_date": report.as_of_date.isoformat(),
        "rows": [
            {
                "customer_id": row.customer_id,
                "customer_code": row.customer_code,
                "customer_name": row.customer_name,
                "current_cents": row.current_cents,
                "d1_30_cents": row.d1_30_cents,
                "d31_60_cents": row.d31_60_cents,
                "d61_90_cents": row.d61_90_cents,
                "over_90_cents": row.over_90_cents,
                "total_cents": row.total_cents,
                "invoices": row.invoices,
            }
            for row in report.rows
        ],
        "totals": {
            "current_cents": report.total_current_cents,
            "d1_30_cents": report.total_d1_30_cents,
            "d31_60_cents": report.total_d31_60_cents,
            "d61_90_cents": report.total_d61_90_cents,
            "over_90_cents": report.total_over_90_cents,
            "total_cents": report.total_cents,
        },
    }


@router.get("/sub-ledger-reconciliation")
def sub_ledger_reconciliation(
    as_of_date: date = Query(..., description="Inclusive as-of date."),
    session: Session = Depends(get_company_session),
) -> dict[str, Any]:
    """Sub-ledger reconciliation canary.

    Returns ``ar_difference_cents`` which should always be zero in a
    healthy company. Non-zero means the AR control account has drifted
    away from the sum of open invoice balances.
    """
    report = build_reconciliation(session, as_of_date=as_of_date)
    return {
        "as_of_date": report.as_of_date.isoformat(),
        "ar_control_account_id": report.ar_control_account_id,
        "ar_control_account_code": report.ar_control_account_code,
        "ar_control_balance_cents": report.ar_control_balance_cents,
        "ar_sub_ledger_cents": report.ar_sub_ledger_cents,
        "ar_difference_cents": report.ar_difference_cents,
    }
