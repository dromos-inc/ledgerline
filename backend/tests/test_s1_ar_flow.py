"""End-to-end tests for Phase 2 / S1 (AR one-liner).

Covers every mutation the AR sub-ledger exposes, plus the two
invariants the plan §12 calls out:

- Reconciliation: after every state transition, the AR control
  account balance must equal the sum of open invoice balances.
- Void cascade: voiding an invoice with active-payment applications
  must 409, naming the applications.

Tests use the FastAPI TestClient for the full HTTP round-trip so a
breakage at any layer (Pydantic, service, trigger) shows up.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

COMPANY_ID = "test-co"


@pytest.fixture
def co(client: TestClient) -> dict[str, Any]:
    """Provision a company + return the key account ids."""
    r = client.post(
        "/api/v1/companies",
        json={
            "id": COMPANY_ID,
            "name": "Test Co",
            "fiscal_year_start_month": 1,
        },
        params={"template": "s_corp_general"},
    )
    assert r.status_code == 201, r.json()
    accounts = client.get(f"/api/v1/companies/{COMPANY_ID}/accounts").json()
    by_code = {a["code"]: a for a in accounts}
    return {
        "ar": by_code["1200"],
        "ap": by_code["2000"],
        "tax_payable": by_code["2200"],
        "cash": by_code["1000"],
        "revenue": by_code["4000"],
    }


def _assert_reconciled(client: TestClient, as_of: date) -> None:
    r = client.get(
        f"/api/v1/companies/{COMPANY_ID}/reports/sub-ledger-reconciliation",
        params={"as_of_date": as_of.isoformat()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ar_difference_cents"] == 0, (
        f"reconciliation drift: control={body['ar_control_balance_cents']} "
        f"sub_ledger={body['ar_sub_ledger_cents']} "
        f"diff={body['ar_difference_cents']}"
    )


def _create_customer(client: TestClient, code: str = "CUST-001", name: str = "Acme") -> int:
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/customers",
        json={"code": code, "name": name},
    )
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def _create_draft_invoice(
    client: TestClient,
    customer_id: int,
    revenue_account_id: int,
    *,
    number: str = "INV-001",
    amount_cents: int = 50000,
    invoice_date: date = date(2026, 4, 1),
    due_offset_days: int = 30,
) -> dict[str, Any]:
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/invoices",
        json={
            "number": number,
            "customer_id": customer_id,
            "invoice_date": invoice_date.isoformat(),
            "due_date": (invoice_date + timedelta(days=due_offset_days)).isoformat(),
            "terms": "net_30",
            "lines": [
                {
                    "account_id": revenue_account_id,
                    "description": "svc",
                    "quantity_milli": 1000,
                    "unit_price_cents": amount_cents,
                }
            ],
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _post_invoice(client: TestClient, invoice_id: int) -> dict[str, Any]:
    r = client.post(f"/api/v1/companies/{COMPANY_ID}/invoices/{invoice_id}/post")
    assert r.status_code == 200, r.json()
    return r.json()


def _pay(
    client: TestClient,
    customer_id: int,
    cash_account_id: int,
    invoice_id: int,
    amount_cents: int,
    *,
    payment_date: date = date(2026, 4, 10),
) -> dict[str, Any]:
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/payments",
        json={
            "customer_id": customer_id,
            "payment_date": payment_date.isoformat(),
            "amount_cents": amount_cents,
            "deposit_account_id": cash_account_id,
            "method": "check",
            "applications": [
                {"invoice_id": invoice_id, "amount_cents": amount_cents}
            ],
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


# --- Customer CRUD ---------------------------------------------------------


def test_customer_crud_happy_path(client: TestClient, co):
    cust_id = _create_customer(client, "CUST-100", "Acme Co")
    r = client.get(f"/api/v1/companies/{COMPANY_ID}/customers/{cust_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Co"

    r = client.patch(
        f"/api/v1/companies/{COMPANY_ID}/customers/{cust_id}",
        json={"name": "Acme Corporation", "notes": "updated"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Corporation"
    assert r.json()["notes"] == "updated"

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/customers/{cust_id}/deactivate")
    assert r.json()["is_active"] is False

    r = client.get(f"/api/v1/companies/{COMPANY_ID}/customers")
    assert cust_id not in [c["id"] for c in r.json()]

    r = client.get(
        f"/api/v1/companies/{COMPANY_ID}/customers",
        params={"include_inactive": True},
    )
    assert cust_id in [c["id"] for c in r.json()]


def test_customer_duplicate_code_is_409(client: TestClient, co):
    _create_customer(client, "DUP-001", "First")
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/customers",
        json={"code": "DUP-001", "name": "Second"},
    )
    assert r.status_code == 409


# --- Invoice lifecycle -----------------------------------------------------


def test_invoice_post_creates_je_and_reconciles(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=50000)
    assert inv["status"] == "draft"
    assert inv["journal_entry_id"] is None

    posted = _post_invoice(client, inv["id"])
    assert posted["status"] == "sent"
    assert posted["journal_entry_id"] is not None
    assert posted["balance_cents"] == 50000

    # Reconciliation: AR control balance = $500, sub-ledger = $500.
    _assert_reconciled(client, date(2026, 4, 1))


def test_invoice_draft_edit_then_post(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=10000)
    assert inv["total_cents"] == 10000

    r = client.patch(
        f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}",
        json={
            "lines": [
                {
                    "account_id": co["revenue"]["id"],
                    "description": "revised",
                    "quantity_milli": 1000,
                    "unit_price_cents": 25000,
                },
                {
                    "account_id": co["revenue"]["id"],
                    "description": "second line",
                    "quantity_milli": 2000,
                    "unit_price_cents": 10000,
                },
            ]
        },
    )
    assert r.status_code == 200, r.json()
    updated = r.json()
    assert updated["total_cents"] == 25000 + 20000  # $450.00
    assert len(updated["lines"]) == 2

    _post_invoice(client, inv["id"])
    _assert_reconciled(client, date(2026, 4, 1))


def test_posted_invoice_patch_is_409(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"])
    _post_invoice(client, inv["id"])

    r = client.patch(
        f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}",
        json={"memo": "after post"},
    )
    assert r.status_code == 409


def test_non_income_account_rejected_on_invoice_line(client: TestClient, co):
    cust_id = _create_customer(client)
    # Try to post to AR directly — that's an asset, not income.
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/invoices",
        json={
            "number": "INV-BAD",
            "customer_id": cust_id,
            "invoice_date": "2026-04-01",
            "due_date": "2026-05-01",
            "terms": "net_30",
            "lines": [
                {
                    "account_id": co["ar"]["id"],  # asset, not income
                    "description": "bad",
                    "quantity_milli": 1000,
                    "unit_price_cents": 10000,
                }
            ],
        },
    )
    assert r.status_code == 400


# --- Payment lifecycle -----------------------------------------------------


def test_partial_payment_rolls_invoice_status(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=100000)
    _post_invoice(client, inv["id"])

    _pay(client, cust_id, co["cash"]["id"], inv["id"], amount_cents=40000)
    r = client.get(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}")
    assert r.json()["status"] == "partial"
    assert r.json()["amount_paid_cents"] == 40000
    assert r.json()["balance_cents"] == 60000
    _assert_reconciled(client, date(2026, 4, 10))


def test_full_payment_marks_paid(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=25000)
    _post_invoice(client, inv["id"])

    _pay(client, cust_id, co["cash"]["id"], inv["id"], amount_cents=25000)
    r = client.get(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}")
    assert r.json()["status"] == "paid"
    assert r.json()["balance_cents"] == 0
    _assert_reconciled(client, date(2026, 4, 10))


def test_payment_void_restores_invoice_balance_and_status(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=50000)
    _post_invoice(client, inv["id"])
    pmt = _pay(client, cust_id, co["cash"]["id"], inv["id"], amount_cents=50000)

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/payments/{pmt['id']}/void")
    assert r.status_code == 200
    assert r.json()["status"] == "void"

    r = client.get(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}")
    assert r.json()["status"] == "sent"
    assert r.json()["amount_paid_cents"] == 0
    assert r.json()["balance_cents"] == 50000
    # Reversal JEs are dated today (the void date), not the original
    # transaction date. Reconciliation is only guaranteed consistent
    # when queried "as of today" after a void — querying as of the
    # payment date would show the payment but not the reversal.
    _assert_reconciled(client, date.today())


def test_payment_over_application_rejected(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=10000)
    _post_invoice(client, inv["id"])

    # Try to apply $150 to a $100 invoice balance — should 400.
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/payments",
        json={
            "customer_id": cust_id,
            "payment_date": "2026-04-10",
            "amount_cents": 15000,
            "deposit_account_id": co["cash"]["id"],
            "method": "check",
            "applications": [
                {"invoice_id": inv["id"], "amount_cents": 15000}
            ],
        },
    )
    assert r.status_code == 400


# --- Invoice void ---------------------------------------------------------


def test_void_invoice_with_active_payment_returns_409(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=20000)
    _post_invoice(client, inv["id"])
    _pay(client, cust_id, co["cash"]["id"], inv["id"], amount_cents=20000)

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}/void")
    assert r.status_code == 409
    assert "applications" in r.json()["detail"]


def test_void_invoice_after_voiding_payment_succeeds(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=20000)
    _post_invoice(client, inv["id"])
    pmt = _pay(client, cust_id, co["cash"]["id"], inv["id"], amount_cents=20000)

    client.post(f"/api/v1/companies/{COMPANY_ID}/payments/{pmt['id']}/void")

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}/void")
    assert r.status_code == 200
    assert r.json()["status"] == "void"
    _assert_reconciled(client, date.today())


def test_void_voided_invoice_is_idempotent(client: TestClient, co):
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=20000)
    _post_invoice(client, inv["id"])

    r1 = client.post(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}/void")
    r2 = client.post(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}/void")
    assert r1.json()["status"] == "void"
    assert r2.json()["status"] == "void"


# --- Reconciliation with unapplied payment credits -----------------------


def test_reconciliation_holds_with_unapplied_payment(client: TestClient, co):
    """A payment with an unapplied portion credits AR for the full amount
    but only the applied portion reduces invoice balances. The
    reconciliation report must still report zero drift because the
    unapplied credit sits on AR as negative balance. Regression test for
    Devin review comment on PR #6."""
    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"], amount_cents=80000)
    _post_invoice(client, inv["id"])

    # Pay $1000 against an $800 invoice: $800 applied, $200 unapplied
    # (customer credit for future invoices).
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/payments",
        json={
            "customer_id": cust_id,
            "payment_date": "2026-04-10",
            "amount_cents": 100000,
            "deposit_account_id": co["cash"]["id"],
            "method": "check",
            "applications": [
                {"invoice_id": inv["id"], "amount_cents": 80000}
            ],
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["applied_cents"] == 80000
    assert r.json()["unapplied_cents"] == 20000

    # Invoice is fully paid.
    r_inv = client.get(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv['id']}")
    assert r_inv.json()["status"] == "paid"
    assert r_inv.json()["balance_cents"] == 0

    # Reconciliation: AR control = $800 Dr - $1000 Cr = -$200.
    # Sub-ledger balances = $0 (invoice fully paid).
    # Unapplied credit = $200.
    # Effective sub-ledger = $0 - $200 = -$200.
    # Difference = -$200 - (-$200) = 0. ✓
    r_rec = client.get(
        f"/api/v1/companies/{COMPANY_ID}/reports/sub-ledger-reconciliation",
        params={"as_of_date": "2026-04-10"},
    )
    assert r_rec.status_code == 200
    body = r_rec.json()
    assert body["ar_unapplied_credits_cents"] == 20000
    assert body["ar_control_balance_cents"] == -20000
    assert body["ar_sub_ledger_cents"] == 0
    assert body["ar_difference_cents"] == 0


# --- AR aging -------------------------------------------------------------


def test_ar_aging_buckets(client: TestClient, co):
    cust_a = _create_customer(client, "CUST-A", "Alpha")
    cust_b = _create_customer(client, "CUST-B", "Bravo")
    # long overdue
    inv1 = _create_draft_invoice(
        client, cust_a, co["revenue"]["id"],
        number="INV-1", amount_cents=100000,
        invoice_date=date(2026, 1, 1),
    )
    _post_invoice(client, inv1["id"])
    # current
    inv2 = _create_draft_invoice(
        client, cust_a, co["revenue"]["id"],
        number="INV-2", amount_cents=50000,
        invoice_date=date(2026, 3, 15),
    )
    _post_invoice(client, inv2["id"])
    # another customer, 1-30 days overdue
    inv3 = _create_draft_invoice(
        client, cust_b, co["revenue"]["id"],
        number="INV-3", amount_cents=30000,
        invoice_date=date(2026, 2, 1),
    )
    _post_invoice(client, inv3["id"])

    r = client.get(
        f"/api/v1/companies/{COMPANY_ID}/reports/ar-aging",
        params={"as_of_date": "2026-04-01"},
    )
    assert r.status_code == 200
    body = r.json()
    # Two customers in the report
    assert len(body["rows"]) == 2
    assert body["totals"]["total_cents"] == 180000

    # Alpha: $1000 in 31_60, $500 current (due date was 2026-04-14)
    alpha_row = next(r for r in body["rows"] if r["customer_code"] == "CUST-A")
    assert alpha_row["d31_60_cents"] == 100000
    assert alpha_row["current_cents"] == 50000

    # Bravo: $300 in 1_30 (due 2026-03-03, 29 days overdue)
    bravo_row = next(r for r in body["rows"] if r["customer_code"] == "CUST-B")
    assert bravo_row["d1_30_cents"] == 30000


# --- Customer delete protection -------------------------------------------


def test_customer_cannot_be_hard_deleted_with_invoices(client: TestClient, co):
    """The trg_customers_no_delete_with_invoices trigger refuses DELETE
    on a customer that has any invoice row. Service layer has no DELETE
    route, so we reach into the DB via a raw session to verify the
    trigger fires. Covers Phase 2 plan §10."""
    from sqlalchemy import text

    from app.db.engines import company_engine
    from app.db.session import company_session

    cust_id = _create_customer(client)
    inv = _create_draft_invoice(client, cust_id, co["revenue"]["id"])
    _post_invoice(client, inv["id"])

    settings = client.app.state.settings
    # Trigger DB engine init.
    engine = company_engine(settings, COMPANY_ID)  # noqa: F841
    with company_session(COMPANY_ID, settings) as sess:
        with pytest.raises(Exception) as excinfo:
            sess.execute(text("DELETE FROM customers WHERE id = :cid"), {"cid": cust_id})
            sess.flush()
        assert "customer" in str(excinfo.value).lower()
