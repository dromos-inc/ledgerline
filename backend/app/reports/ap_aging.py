"""AP aging report.

Mirror of ``ar_aging``. Buckets outstanding bill balances by how
overdue they are, per vendor.

Semantics:
- "Outstanding" = ``bills`` with status in ('open', 'partial') and
  ``total_cents - amount_paid_cents > 0``. Voided, paid, and draft
  bills drop out.
- "Days overdue" = ``as_of_date - due_date``. Values <= 0 land in the
  ``current`` bucket.
- Report groups by vendor; vendors with no outstanding balance are
  omitted unless ``include_zero_balance=True``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.contact import Vendor

# Bucket labels in the order they appear in the report.
BUCKET_LABELS = ("current", "1_30", "31_60", "61_90", "over_90")


@dataclass
class AgingRow:
    """One vendor's aging breakdown."""

    vendor_id: int
    vendor_code: str
    vendor_name: str
    current_cents: int = 0
    d1_30_cents: int = 0
    d31_60_cents: int = 0
    d61_90_cents: int = 0
    over_90_cents: int = 0
    total_cents: int = 0
    # Per-bill detail, optional for drill-in.
    bills: list[dict] = field(default_factory=list)


@dataclass
class AgingReport:
    """Full AP aging for a company as of a date."""

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


def build_ap_aging(
    session: Session,
    *,
    as_of_date: date,
    include_zero_balance: bool = False,
) -> AgingReport:
    """Compute the AP aging report as of ``as_of_date``."""
    stmt = (
        select(Bill)
        .where(Bill.status.in_(("open", "partial")))
        .where(Bill.bill_date <= as_of_date)
        .order_by(Bill.due_date, Bill.id)
    )
    bills = list(session.execute(stmt).scalars().all())

    # Load all referenced vendors in one round-trip.
    vendor_ids = {b.vendor_id for b in bills}
    vendors_by_id: dict[int, Vendor] = {}
    if vendor_ids:
        v_stmt = select(Vendor).where(Vendor.id.in_(vendor_ids))
        for vendor in session.execute(v_stmt).scalars().all():
            vendors_by_id[vendor.id] = vendor

    # Aggregate.
    rows_by_vendor: dict[int, AgingRow] = {}
    for bill in bills:
        balance = bill.total_cents - bill.amount_paid_cents
        if balance <= 0:
            continue
        days_overdue = (as_of_date - bill.due_date).days
        bucket = _bucket_for_days(days_overdue)

        if bill.vendor_id not in rows_by_vendor:
            v = vendors_by_id.get(bill.vendor_id)
            rows_by_vendor[bill.vendor_id] = AgingRow(
                vendor_id=bill.vendor_id,
                vendor_code=v.code if v else f"#{bill.vendor_id}",
                vendor_name=v.name if v else f"Vendor {bill.vendor_id}",
            )
        row = rows_by_vendor[bill.vendor_id]

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
        row.bills.append(
            {
                "bill_id": bill.id,
                "number": bill.number,
                "bill_date": bill.bill_date.isoformat(),
                "due_date": bill.due_date.isoformat(),
                "days_overdue": days_overdue,
                "bucket": bucket,
                "balance_cents": balance,
                "total_cents": bill.total_cents,
                "amount_paid_cents": bill.amount_paid_cents,
            }
        )

    # Sort vendors by total desc, then by name.
    ordered_rows = sorted(
        rows_by_vendor.values(),
        key=lambda r: (-r.total_cents, r.vendor_name),
    )

    # Optionally include zero-balance vendors.
    if include_zero_balance:
        for vid, vendor in vendors_by_id.items():
            if vid not in rows_by_vendor:
                ordered_rows.append(
                    AgingRow(
                        vendor_id=vid,
                        vendor_code=vendor.code,
                        vendor_name=vendor.name,
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