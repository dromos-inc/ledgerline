"""AR aging report.

Buckets outstanding invoice balances by how overdue they are, per
customer. Standard buckets: current (not yet due), 1-30, 31-60,
61-90, 90+ days past due.

Semantics:
- "Outstanding" = ``invoices`` with status in ('sent', 'partial') and
  ``total_cents - amount_paid_cents > 0``. Voided and paid invoices
  drop out.
- "Days overdue" = ``as_of_date - due_date``. Values <= 0 land in the
  ``current`` bucket.
- Report groups by customer; customers with no outstanding balance
  are omitted unless ``include_zero_balance=True``.

Phase 2 §12 test coverage: a customer with two invoices (one current,
one 45 days overdue) should show two rows in different buckets and
a total that sums both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contact import Customer
from app.models.invoice import Invoice

# Bucket labels in the order they appear in the report.
BUCKET_LABELS = ("current", "1_30", "31_60", "61_90", "over_90")


@dataclass
class AgingRow:
    """One customer's aging breakdown."""

    customer_id: int
    customer_code: str
    customer_name: str
    current_cents: int = 0
    d1_30_cents: int = 0
    d31_60_cents: int = 0
    d61_90_cents: int = 0
    over_90_cents: int = 0
    total_cents: int = 0
    # Per-invoice detail, optional for drill-in.
    invoices: list[dict] = field(default_factory=list)


@dataclass
class AgingReport:
    """Full AR aging for a company as of a date."""

    as_of_date: date
    rows: list[AgingRow] = field(default_factory=list)
    total_current_cents: int = 0
    total_d1_30_cents: int = 0
    total_d31_60_cents: int = 0
    total_d61_90_cents: int = 0
    total_over_90_cents: int = 0
    total_cents: int = 0


def _bucket_for_days(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "over_90"


def build_ar_aging(
    session: Session,
    *,
    as_of_date: date,
    include_zero_balance: bool = False,
) -> AgingReport:
    """Compute the aging report as of ``as_of_date``."""
    # Pull every potentially-outstanding invoice in one query, then
    # bucket in Python. Safer than trying to express the bucket CASE
    # in SQLite's WHEN-THEN when we want per-row detail anyway.
    stmt = (
        select(Invoice)
        .where(Invoice.status.in_(("sent", "partial")))
        .where(Invoice.invoice_date <= as_of_date)
        .order_by(Invoice.due_date, Invoice.id)
    )
    invoices = list(session.execute(stmt).scalars().all())

    # Load all referenced customers in one round-trip.
    customer_ids = {inv.customer_id for inv in invoices}
    customers_by_id: dict[int, Customer] = {}
    if customer_ids:
        cust_stmt = select(Customer).where(Customer.id.in_(customer_ids))
        for customer in session.execute(cust_stmt).scalars().all():
            customers_by_id[customer.id] = customer

    # Aggregate.
    rows_by_customer: dict[int, AgingRow] = {}
    for inv in invoices:
        balance = inv.total_cents - inv.amount_paid_cents
        if balance <= 0:
            continue
        days_overdue = (as_of_date - inv.due_date).days
        bucket = _bucket_for_days(days_overdue)

        if inv.customer_id not in rows_by_customer:
            c = customers_by_id.get(inv.customer_id)
            rows_by_customer[inv.customer_id] = AgingRow(
                customer_id=inv.customer_id,
                customer_code=c.code if c else f"#{inv.customer_id}",
                customer_name=c.name if c else f"Customer {inv.customer_id}",
            )
        row = rows_by_customer[inv.customer_id]

        if bucket == "current":
            row.current_cents += balance
        elif bucket == "1_30":
            row.d1_30_cents += balance
        elif bucket == "31_60":
            row.d31_60_cents += balance
        elif bucket == "61_90":
            row.d61_90_cents += balance
        else:
            row.over_90_cents += balance
        row.total_cents += balance
        row.invoices.append(
            {
                "invoice_id": inv.id,
                "number": inv.number,
                "invoice_date": inv.invoice_date.isoformat(),
                "due_date": inv.due_date.isoformat(),
                "days_overdue": days_overdue,
                "bucket": bucket,
                "balance_cents": balance,
                "total_cents": inv.total_cents,
                "amount_paid_cents": inv.amount_paid_cents,
            }
        )

    # Sort customers by total desc, then by name.
    ordered_rows = sorted(
        rows_by_customer.values(),
        key=lambda r: (-r.total_cents, r.customer_name),
    )

    # Optionally include zero-balance customers.
    if include_zero_balance:
        for cid, customer in customers_by_id.items():
            if cid not in rows_by_customer:
                ordered_rows.append(
                    AgingRow(
                        customer_id=cid,
                        customer_code=customer.code,
                        customer_name=customer.name,
                    )
                )

    report = AgingReport(as_of_date=as_of_date, rows=ordered_rows)
    for row in ordered_rows:
        report.total_current_cents += row.current_cents
        report.total_d1_30_cents += row.d1_30_cents
        report.total_d31_60_cents += row.d31_60_cents
        report.total_d61_90_cents += row.d61_90_cents
        report.total_over_90_cents += row.over_90_cents
        report.total_cents += row.total_cents
    return report


def days_between(a: date, b: date) -> int:
    """Helper exposed for tests."""
    return (a - b).days if isinstance(a - b, timedelta) else 0
