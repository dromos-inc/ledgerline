"""End-to-end tests for Phase 2 / S2 (AP one-liner).

Mirror of ``test_s1_ar_flow``. Covers every mutation the AP sub-ledger
exposes, plus the two invariants called out in the plan §12:

- AP reconciliation: after every state transition, the AP control
  account balance must equal the net of open bill balances and
  unapplied bill_payment credits.
- Void cascade: voiding a bill with active bill_payment applications
  must 409, naming the applications.

Plus one integration test that verifies AR + AP coexist on the same
company without interference.
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
    # Pick any expense account from the seed template. The S-corp
    # template has a 5xxx expense section; by asking "first expense"
    # rather than pinning a specific code we survive minor template
    # reshufflings between phases.
    expense = next((a for a in accounts if a["type"] == "expense"), None)
    assert expense is not None, "seed template should include at least one expense account"
    return {
        "ar": by_code["1200"],
        "ap": by_code["2000"],
        "tax_payable": by_code["2200"],
        "cash": by_code["1000"],
        "revenue": by_code["4000"],
        "expense": expense,
    }


def _assert_reconciled(client: TestClient, as_of: date) -> None:
    r = client.get(
        f"/api/v1/companies/{COMPANY_ID}/reports/sub-ledger-reconciliation",
        params={"as_of_date": as_of.isoformat()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ar_difference_cents"] == 0, (
        f"AR reconciliation drift: control={body['ar_control_balance_cents']} "
        f"sub_ledger={body['ar_sub_ledger_cents']} "
        f"diff={body['ar_difference_cents']}"
    )
    assert body["ap_difference_cents"] == 0, (
        f"AP reconciliation drift: control={body['ap_control_balance_cents']} "
        f"sub_ledger={body['ap_sub_ledger_cents']} "
        f"diff={body['ap_difference_cents']}"
    )


def _create_vendor(
    client: TestClient, code: str = "VEND-001", name: str = "Acme Supplies"
) -> int:
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/vendors",
        json={"code": code, "name": name},
    )
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def _create_draft_bill(
    client: TestClient,
    vendor_id: int,
    expense_account_id: int,
    *,
    number: str = "BILL-001",
    amount_cents: int = 50000,
    bill_date: date = date(2026, 4, 1),
    due_offset_days: int = 30,
) -> dict[str, Any]:
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bills",
        json={
            "number": number,
            "vendor_id": vendor_id,
            "bill_date": bill_date.isoformat(),
            "due_date": (bill_date + timedelta(days=due_offset_days)).isoformat(),
            "terms": "net_30",
            "lines": [
                {
                    "account_id": expense_account_id,
                    "description": "office supplies",
                    "quantity_milli": 1000,
                    "unit_price_cents": amount_cents,
                }
            ],
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _post_bill(client: TestClient, bill_id: int) -> dict[str, Any]:
    r = client.post(f"/api/v1/companies/{COMPANY_ID}/bills/{bill_id}/post")
    assert r.status_code == 200, r.json()
    return r.json()


def _pay_bill(
    client: TestClient,
    vendor_id: int,
    cash_account_id: int,
    bill_id: int,
    amount_cents: int,
    *,
    payment_date: date = date(2026, 4, 10),
) -> dict[str, Any]:
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bill-payments",
        json={
            "vendor_id": vendor_id,
            "payment_date": payment_date.isoformat(),
            "amount_cents": amount_cents,
            "payout_account_id": cash_account_id,
            "method": "check",
            "applications": [
                {"bill_id": bill_id, "amount_cents": amount_cents}
            ],
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


# --- Vendor CRUD ---------------------------------------------------------


def test_vendor_crud_happy_path(client: TestClient, co):
    vend_id = _create_vendor(client, "VEND-100", "Acme Supplies")
    r = client.get(f"/api/v1/companies/{COMPANY_ID}/vendors/{vend_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Supplies"

    r = client.patch(
        f"/api/v1/companies/{COMPANY_ID}/vendors/{vend_id}",
        json={"name": "Acme Supplies LLC", "is_1099": True, "notes": "updated"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Supplies LLC"
    assert r.json()["is_1099"] is True
    assert r.json()["notes"] == "updated"

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/vendors/{vend_id}/deactivate")
    assert r.json()["is_active"] is False

    r = client.get(f"/api/v1/companies/{COMPANY_ID}/vendors")
    assert vend_id not in [v["id"] for v in r.json()]

    r = client.get(
        f"/api/v1/companies/{COMPANY_ID}/vendors",
        params={"include_inactive": True},
    )
    assert vend_id in [v["id"] for v in r.json()]


def test_vendor_duplicate_code_is_409(client: TestClient, co):
    _create_vendor(client, "DUP-001", "First")
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/vendors",
        json={"code": "DUP-001", "name": "Second"},
    )
    assert r.status_code == 409


def test_vendor_non_expense_default_account_rejected(client: TestClient, co):
    # Try to default-expense-account a revenue account — that's income, not expense.
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/vendors",
        json={
            "code": "VEND-BAD",
            "name": "Bad Default",
            "default_expense_account_id": co["revenue"]["id"],
        },
    )
    assert r.status_code == 400


# --- Bill lifecycle -----------------------------------------------------


def test_bill_post_creates_je_and_reconciles(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=50000)
    assert bill["status"] == "draft"
    assert bill["journal_entry_id"] is None

    posted = _post_bill(client, bill["id"])
    assert posted["status"] == "open"
    assert posted["journal_entry_id"] is not None
    assert posted["balance_cents"] == 50000
    assert posted["approved_at"] is not None

    _assert_reconciled(client, date(2026, 4, 1))


def test_bill_draft_edit_then_post(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=10000)
    assert bill["total_cents"] == 10000

    r = client.patch(
        f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}",
        json={
            "lines": [
                {
                    "account_id": co["expense"]["id"],
                    "description": "revised",
                    "quantity_milli": 1000,
                    "unit_price_cents": 25000,
                },
                {
                    "account_id": co["expense"]["id"],
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

    _post_bill(client, bill["id"])
    _assert_reconciled(client, date(2026, 4, 1))


def test_posted_bill_patch_is_409(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"])
    _post_bill(client, bill["id"])

    r = client.patch(
        f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}",
        json={"memo": "after post"},
    )
    assert r.status_code == 409


def test_non_expense_account_rejected_on_bill_line(client: TestClient, co):
    vend_id = _create_vendor(client)
    # Try to post a bill line to revenue — that's income, not expense.
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bills",
        json={
            "number": "BILL-BAD",
            "vendor_id": vend_id,
            "bill_date": "2026-04-01",
            "due_date": "2026-05-01",
            "terms": "net_30",
            "lines": [
                {
                    "account_id": co["revenue"]["id"],  # income, not expense
                    "description": "bad",
                    "quantity_milli": 1000,
                    "unit_price_cents": 10000,
                }
            ],
        },
    )
    assert r.status_code == 400


def test_bill_line_can_target_asset_account(client: TestClient, co):
    """Bills that capitalize costs debit an asset account, not expense."""
    vend_id = _create_vendor(client)
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bills",
        json={
            "number": "BILL-CAPEX",
            "vendor_id": vend_id,
            "bill_date": "2026-04-01",
            "due_date": "2026-05-01",
            "terms": "net_30",
            "lines": [
                {
                    "account_id": co["cash"]["id"],  # asset
                    "description": "capex purchase",
                    "quantity_milli": 1000,
                    "unit_price_cents": 99999,
                }
            ],
        },
    )
    assert r.status_code == 201, r.json()


# --- BillPayment lifecycle ----------------------------------------------


def test_partial_bill_payment_rolls_bill_status(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=100000)
    _post_bill(client, bill["id"])

    _pay_bill(client, vend_id, co["cash"]["id"], bill["id"], amount_cents=40000)
    r = client.get(f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}")
    assert r.json()["status"] == "partial"
    assert r.json()["amount_paid_cents"] == 40000
    assert r.json()["balance_cents"] == 60000
    _assert_reconciled(client, date(2026, 4, 10))


def test_full_bill_payment_marks_paid(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=25000)
    _post_bill(client, bill["id"])

    _pay_bill(client, vend_id, co["cash"]["id"], bill["id"], amount_cents=25000)
    r = client.get(f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}")
    assert r.json()["status"] == "paid"
    assert r.json()["balance_cents"] == 0
    _assert_reconciled(client, date(2026, 4, 10))


def test_bill_payment_void_restores_bill_balance_and_status(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=50000)
    _post_bill(client, bill["id"])
    pmt = _pay_bill(client, vend_id, co["cash"]["id"], bill["id"], amount_cents=50000)

    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bill-payments/{pmt['id']}/void"
    )
    assert r.status_code == 200
    assert r.json()["status"] == "void"

    r = client.get(f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}")
    assert r.json()["status"] == "open"
    assert r.json()["amount_paid_cents"] == 0
    assert r.json()["balance_cents"] == 50000
    _assert_reconciled(client, date.today())


def test_bill_payment_over_application_rejected(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=10000)
    _post_bill(client, bill["id"])

    # Try to apply $150 to a $100 bill balance — should 400.
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bill-payments",
        json={
            "vendor_id": vend_id,
            "payment_date": "2026-04-10",
            "amount_cents": 15000,
            "payout_account_id": co["cash"]["id"],
            "method": "check",
            "applications": [{"bill_id": bill["id"], "amount_cents": 15000}],
        },
    )
    assert r.status_code == 400


# --- Bill void -----------------------------------------------------------


def test_void_bill_with_active_payment_returns_409(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=20000)
    _post_bill(client, bill["id"])
    _pay_bill(client, vend_id, co["cash"]["id"], bill["id"], amount_cents=20000)

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}/void")
    assert r.status_code == 409
    assert "applications" in r.json()["detail"]


def test_void_bill_after_voiding_payment_succeeds(client: TestClient, co):
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=20000)
    _post_bill(client, bill["id"])
    pmt = _pay_bill(client, vend_id, co["cash"]["id"], bill["id"], amount_cents=20000)

    client.post(f"/api/v1/companies/{COMPANY_ID}/bill-payments/{pmt['id']}/void")

    r = client.post(f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}/void")
    assert r.status_code == 200
    assert r.json()["status"] == "void"
    _assert_reconciled(client, date.today())


# --- Reconciliation with unapplied bill_payment credits ------------------


def test_reconciliation_holds_with_unapplied_bill_payment(client: TestClient, co):
    """A bill_payment with an unapplied portion debits AP for the full
    amount but only the applied portion reduces bill balances. The
    reconciliation report must still report zero drift because the
    unapplied vendor credit sits on AP as a negative balance. Mirror
    of the AR regression test landed with PR #7."""
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=80000)
    _post_bill(client, bill["id"])

    # Pay $1000 against an $800 bill: $800 applied, $200 unapplied
    # (vendor credit for future bills).
    r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/bill-payments",
        json={
            "vendor_id": vend_id,
            "payment_date": "2026-04-10",
            "amount_cents": 100000,
            "payout_account_id": co["cash"]["id"],
            "method": "check",
            "applications": [{"bill_id": bill["id"], "amount_cents": 80000}],
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["applied_cents"] == 80000
    assert r.json()["unapplied_cents"] == 20000

    # Bill is fully paid.
    r_bill = client.get(f"/api/v1/companies/{COMPANY_ID}/bills/{bill['id']}")
    assert r_bill.json()["status"] == "paid"
    assert r_bill.json()["balance_cents"] == 0

    # Reconciliation math (AP side, sign-flipped from AR):
    # AP is credit-normal. Bill posts Cr AP $800; bill_payment posts Dr
    # AP $1000. Raw Dr-Cr on AP = $200. Negated (to match sub-ledger
    # convention) = -$200.
    # Open bill balance = $0 (fully paid).
    # Unapplied credit = $200.
    # Effective sub-ledger = $0 - $200 = -$200.
    # Difference = -$200 - (-$200) = 0. ✓
    r_rec = client.get(
        f"/api/v1/companies/{COMPANY_ID}/reports/sub-ledger-reconciliation",
        params={"as_of_date": "2026-04-10"},
    )
    assert r_rec.status_code == 200
    body = r_rec.json()
    assert body["ap_unapplied_credits_cents"] == 20000
    assert body["ap_control_balance_cents"] == -20000
    assert body["ap_sub_ledger_cents"] == 0
    assert body["ap_difference_cents"] == 0


# --- AP aging ------------------------------------------------------------


def test_ap_aging_buckets(client: TestClient, co):
    vend_a = _create_vendor(client, "VEND-A", "Alpha Supplies")
    vend_b = _create_vendor(client, "VEND-B", "Bravo Rentals")
    # long overdue
    bill1 = _create_draft_bill(
        client, vend_a, co["expense"]["id"],
        number="BILL-1", amount_cents=100000,
        bill_date=date(2026, 1, 1),
    )
    _post_bill(client, bill1["id"])
    # current
    bill2 = _create_draft_bill(
        client, vend_a, co["expense"]["id"],
        number="BILL-2", amount_cents=50000,
        bill_date=date(2026, 3, 15),
    )
    _post_bill(client, bill2["id"])
    # another vendor, 1-30 days overdue
    bill3 = _create_draft_bill(
        client, vend_b, co["expense"]["id"],
        number="BILL-3", amount_cents=30000,
        bill_date=date(2026, 2, 1),
    )
    _post_bill(client, bill3["id"])

    r = client.get(
        f"/api/v1/companies/{COMPANY_ID}/reports/ap-aging",
        params={"as_of_date": "2026-04-01"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 2
    assert body["totals"]["total_cents"] == 180000

    alpha_row = next(r for r in body["rows"] if r["vendor_code"] == "VEND-A")
    # Alpha: $1000 in 31_60 bucket (bill1 due 2026-01-31, ~60 days
    # overdue by 2026-04-01), $500 current (bill2 due 2026-04-14, not
    # yet due as of 2026-04-01).
    assert alpha_row["d31_60_cents"] == 100000
    assert alpha_row["current_cents"] == 50000

    bravo_row = next(r for r in body["rows"] if r["vendor_code"] == "VEND-B")
    assert bravo_row["d1_30_cents"] == 30000


# --- Vendor delete protection --------------------------------------------


def test_vendor_cannot_be_hard_deleted_with_bills(client: TestClient, co):
    """The trg_vendors_no_delete_with_bills trigger refuses DELETE on a
    vendor that has any bill row. Service layer has no DELETE route,
    so we reach into the DB via a raw session to verify the trigger
    fires. Mirror of the customer delete-protection test."""
    from sqlalchemy import text

    from app.db.engines import company_engine
    from app.db.session import company_session

    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"])
    _post_bill(client, bill["id"])

    settings = client.app.state.settings
    engine = company_engine(settings, COMPANY_ID)  # noqa: F841
    with company_session(COMPANY_ID, settings) as sess:
        with pytest.raises(Exception) as excinfo:
            sess.execute(text("DELETE FROM vendors WHERE id = :vid"), {"vid": vend_id})
            sess.flush()
        assert "vendor" in str(excinfo.value).lower()


# --- AR + AP coexistence ------------------------------------------------


def test_ar_and_ap_coexist_on_same_company(client: TestClient, co):
    """Ensure creating invoices + bills + payments + bill_payments on
    the same company leaves both sub-ledgers reconciled. Prevents any
    S2 change from regressing the S1 invariant."""
    # AR side
    cust_r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/customers",
        json={"code": "C-1", "name": "Customer"},
    )
    assert cust_r.status_code == 201
    cust_id = cust_r.json()["id"]

    inv_r = client.post(
        f"/api/v1/companies/{COMPANY_ID}/invoices",
        json={
            "number": "INV-1",
            "customer_id": cust_id,
            "invoice_date": "2026-04-01",
            "due_date": "2026-05-01",
            "terms": "net_30",
            "lines": [{
                "account_id": co["revenue"]["id"],
                "description": "svc",
                "quantity_milli": 1000,
                "unit_price_cents": 80000,
            }],
        },
    )
    assert inv_r.status_code == 201
    inv_id = inv_r.json()["id"]
    client.post(f"/api/v1/companies/{COMPANY_ID}/invoices/{inv_id}/post")

    # AP side
    vend_id = _create_vendor(client)
    bill = _create_draft_bill(client, vend_id, co["expense"]["id"], amount_cents=30000)
    _post_bill(client, bill["id"])
    _pay_bill(client, vend_id, co["cash"]["id"], bill["id"], amount_cents=15000)

    # Both invariants hold.
    _assert_reconciled(client, date(2026, 4, 10))