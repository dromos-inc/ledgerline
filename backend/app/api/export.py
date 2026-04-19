"""CSV export endpoints.

PRD §11.1: every list view and every report is exportable to CSV. The
response content type is ``text/csv`` with a filename suggestion.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import (
    company_session,
    get_company_session,
    registry_session,
)
from app.export.csv import cents_to_dollars, to_csv
from app.export.json_dump import dump_company
from app.models.registry import Company
from app.reports.balance_sheet import build_balance_sheet
from app.reports.basis import Basis
from app.reports.profit_loss import build_profit_loss
from app.reports.trial_balance import build_trial_balance
from app.services import account as account_service
from app.services import customer as customer_service
from app.services import journal as journal_service
from app.services import register as register_service

router = APIRouter(
    prefix="/companies/{company_id}/export",
    tags=["export"],
)


def _csv_response(body: str, filename: str) -> Response:
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Lists ------------------------------------------------------------------


@router.get("/accounts.csv")
def accounts_csv(
    include_inactive: bool = Query(default=False),
    session: Session = Depends(get_company_session),
) -> Response:
    accounts = account_service.list_accounts(session, include_inactive=include_inactive)
    header = ["code", "name", "type", "subtype", "is_active", "description"]
    rows = [
        (
            a.code,
            a.name,
            a.type.value,
            a.subtype or "",
            "true" if a.is_active else "false",
            a.description or "",
        )
        for a in accounts
    ]
    return _csv_response(to_csv(header, rows), "accounts.csv")


@router.get("/customers.csv")
def customers_csv(
    include_inactive: bool = Query(default=False),
    q: Optional[str] = Query(default=None),
    session: Session = Depends(get_company_session),
) -> Response:
    customers = customer_service.list_customers(
        session, include_inactive=include_inactive, query=q
    )
    header = [
        "code",
        "name",
        "company",
        "email",
        "phone",
        "tax_id",
        "billing_address",
        "shipping_address",
        "default_terms",
        "default_income_account_id",
        "default_tax_code_id",
        "is_active",
        "notes",
    ]
    rows = [
        (
            c.code,
            c.name,
            c.company or "",
            c.email or "",
            c.phone or "",
            c.tax_id or "",
            c.billing_address or "",
            c.shipping_address or "",
            c.default_terms,
            c.default_income_account_id if c.default_income_account_id is not None else "",
            c.default_tax_code_id if c.default_tax_code_id is not None else "",
            "true" if c.is_active else "false",
            c.notes or "",
        )
        for c in customers
    ]
    return _csv_response(to_csv(header, rows), "customers.csv")


@router.get("/journal-entries.csv")
def journal_entries_csv(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_company_session),
) -> Response:
    entries, _total = journal_service.list_entries(
        session,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        limit=10000,
    )
    header = [
        "entry_id",
        "entry_date",
        "posting_date",
        "status",
        "reference",
        "memo",
        "line_number",
        "account_id",
        "debit",
        "credit",
        "line_memo",
    ]
    rows = []
    for entry in entries:
        for line in entry.lines:
            rows.append(
                (
                    entry.id,
                    entry.entry_date.isoformat(),
                    entry.posting_date.isoformat(),
                    entry.status.value,
                    entry.reference or "",
                    entry.memo or "",
                    line.line_number,
                    line.account_id,
                    cents_to_dollars(line.debit_cents),
                    cents_to_dollars(line.credit_cents),
                    line.memo or "",
                )
            )
    return _csv_response(to_csv(header, rows), "journal-entries.csv")


@router.get("/register.csv")
def register_csv(
    account_id: int = Query(...),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    session: Session = Depends(get_company_session),
) -> Response:
    reg = register_service.build_register(
        session, account_id, start_date=start_date, end_date=end_date
    )
    header = [
        "entry_date",
        "posting_date",
        "reference",
        "memo",
        "debit",
        "credit",
        "running_balance",
    ]
    rows = [
        (
            row.entry_date.isoformat(),
            row.posting_date.isoformat(),
            row.reference or "",
            row.memo or "",
            cents_to_dollars(row.debit_cents),
            cents_to_dollars(row.credit_cents),
            cents_to_dollars(row.running_balance_cents),
        )
        for row in reg.rows
    ]
    filename = f"register-{reg.account_code}.csv"
    return _csv_response(to_csv(header, rows), filename)


# --- Reports ---------------------------------------------------------------


@router.get("/reports/trial-balance.csv")
def trial_balance_csv(
    as_of_date: date = Query(...),
    basis: Basis = Query(default=Basis.ACCRUAL),
    session: Session = Depends(get_company_session),
) -> Response:
    tb = build_trial_balance(session, as_of_date=as_of_date, basis=basis)
    header = ["code", "name", "type", "debit", "credit"]
    rows = [
        (
            row.account_code,
            row.account_name,
            row.account_type.value,
            cents_to_dollars(row.debit_cents),
            cents_to_dollars(row.credit_cents),
        )
        for row in tb.rows
    ]
    rows.append(
        (
            "",
            "TOTAL",
            "",
            cents_to_dollars(tb.total_debit_cents),
            cents_to_dollars(tb.total_credit_cents),
        )
    )
    return _csv_response(to_csv(header, rows), f"trial-balance-{as_of_date}.csv")


@router.get("/reports/profit-loss.csv")
def profit_loss_csv(
    start_date: date = Query(...),
    end_date: date = Query(...),
    basis: Basis = Query(default=Basis.ACCRUAL),
    session: Session = Depends(get_company_session),
) -> Response:
    pl = build_profit_loss(
        session, start_date=start_date, end_date=end_date, basis=basis
    )
    header = ["section", "code", "name", "amount"]
    rows = []
    for row in pl.income.rows:
        rows.append(("Income", row.account_code, row.account_name, cents_to_dollars(row.amount_cents)))
    rows.append(("", "", "Total Income", cents_to_dollars(pl.income.subtotal_cents)))
    for row in pl.expenses.rows:
        rows.append(("Expenses", row.account_code, row.account_name, cents_to_dollars(row.amount_cents)))
    rows.append(("", "", "Total Expenses", cents_to_dollars(pl.expenses.subtotal_cents)))
    rows.append(("", "", "Net Income", cents_to_dollars(pl.net_income_cents)))
    return _csv_response(
        to_csv(header, rows), f"profit-loss-{start_date}-to-{end_date}.csv"
    )


@router.get("/company.json")
def full_company_json(
    company_id: str,
    request: Request,
) -> dict[str, Any]:
    """Full-company JSON export. Round-trip safe."""
    settings: Settings = request.app.state.settings
    with registry_session(settings) as reg_sess, company_session(
        company_id, settings
    ) as co_sess:
        company = reg_sess.get(Company, company_id)
        if company is None:
            raise HTTPException(status_code=404, detail=f"company {company_id!r} not found")
        return dump_company(reg_sess, co_sess, company_id)


@router.get("/reports/balance-sheet.csv")
def balance_sheet_csv(
    as_of_date: date = Query(...),
    basis: Basis = Query(default=Basis.ACCRUAL),
    session: Session = Depends(get_company_session),
) -> Response:
    bs = build_balance_sheet(session, as_of_date=as_of_date, basis=basis)
    header = ["section", "code", "name", "balance"]
    rows = []
    for section in (bs.assets, bs.liabilities, bs.equity):
        for row in section.rows:
            rows.append(
                (
                    section.label,
                    row.account_code,
                    row.account_name,
                    cents_to_dollars(row.balance_cents),
                )
            )
        rows.append(("", "", f"Total {section.label}", cents_to_dollars(section.subtotal_cents)))
    rows.append(
        (
            "",
            "",
            "Difference (A - L - E)",
            cents_to_dollars(bs.equation_difference_cents),
        )
    )
    return _csv_response(to_csv(header, rows), f"balance-sheet-{as_of_date}.csv")
