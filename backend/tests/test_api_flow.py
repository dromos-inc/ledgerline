"""End-to-end API flow test.

Walks through the PRD's Phase 1 exit criteria via HTTP:
1. Create a company.
2. Create a chart of accounts.
3. Post a couple of journal entries.
4. Read the register.
5. Attempt illegal operations and see them rejected.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_full_phase1_flow(client: TestClient) -> None:
    # 1. Create a company.
    resp = client.post(
        "/api/v1/companies",
        json={
            "id": "dromos-inc",
            "name": "Dromos Inc.",
            "entity_type": "s_corp",
            "tax_basis": "accrual",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "dromos-inc"
    assert body["entity_type"] == "s_corp"

    # Listing returns the new company.
    resp = client.get("/api/v1/companies")
    assert resp.status_code == 200
    assert any(c["id"] == "dromos-inc" for c in resp.json())

    # 2. Create a chart of accounts.
    accounts = [
        {"code": "1000", "name": "Cash", "type": "asset"},
        {"code": "4000", "name": "Service Revenue", "type": "income"},
        {"code": "5000", "name": "Rent Expense", "type": "expense"},
    ]
    created_ids: dict[str, int] = {}
    for a in accounts:
        resp = client.post("/api/v1/companies/dromos-inc/accounts", json=a)
        assert resp.status_code == 201, resp.text
        created_ids[a["code"]] = resp.json()["id"]

    # Duplicate code rejected.
    resp = client.post(
        "/api/v1/companies/dromos-inc/accounts",
        json={"code": "1000", "name": "Cash Again", "type": "asset"},
    )
    assert resp.status_code == 409

    # 3. Create + post a balanced entry.
    entry = {
        "entry_date": "2026-01-15",
        "reference": "INV-001",
        "memo": "First client invoice",
        "lines": [
            {"account_id": created_ids["1000"], "debit_cents": 10000},
            {"account_id": created_ids["4000"], "credit_cents": 10000},
        ],
    }
    resp = client.post(
        "/api/v1/companies/dromos-inc/journal-entries", json=entry
    )
    assert resp.status_code == 201, resp.text
    entry_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"

    # Post it.
    resp = client.post(
        f"/api/v1/companies/dromos-inc/journal-entries/{entry_id}/post"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "posted"

    # 4. A second entry: pay rent from cash.
    entry2 = {
        "entry_date": "2026-01-31",
        "memo": "Rent for January",
        "lines": [
            {"account_id": created_ids["5000"], "debit_cents": 3000},
            {"account_id": created_ids["1000"], "credit_cents": 3000},
        ],
    }
    resp = client.post(
        "/api/v1/companies/dromos-inc/journal-entries", json=entry2
    )
    entry2_id = resp.json()["id"]
    client.post(f"/api/v1/companies/dromos-inc/journal-entries/{entry2_id}/post")

    # 5. Register for cash: two posted rows, +10000 then -3000 = +7000.
    cash_id = created_ids["1000"]
    resp = client.get(
        f"/api/v1/companies/dromos-inc/accounts/{cash_id}/register"
    )
    assert resp.status_code == 200
    reg = resp.json()
    assert reg["opening_balance_cents"] == 0
    assert len(reg["rows"]) == 2
    assert reg["closing_balance_cents"] == 7000

    # 6. Imbalanced entry: rejected at schema level (Pydantic).
    resp = client.post(
        "/api/v1/companies/dromos-inc/journal-entries",
        json={
            "entry_date": "2026-02-01",
            "lines": [
                {"account_id": cash_id, "debit_cents": 100},
                {"account_id": created_ids["4000"], "credit_cents": 200},
            ],
        },
    )
    assert resp.status_code == 422

    # 7. Posted entry cannot be deleted via DELETE, only voided.
    resp = client.delete(
        f"/api/v1/companies/dromos-inc/journal-entries/{entry_id}"
    )
    assert resp.status_code == 409

    # Void creates a reversal and flips the original to void.
    resp = client.post(
        f"/api/v1/companies/dromos-inc/journal-entries/{entry_id}/void",
        json={"memo": "Customer disputed invoice"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"

    # Cash register now: +10000, -3000, -10000 = -3000.
    resp = client.get(
        f"/api/v1/companies/dromos-inc/accounts/{cash_id}/register"
    )
    assert resp.json()["closing_balance_cents"] == -3000
    assert len(resp.json()["rows"]) == 3


def test_cannot_use_deactivated_account(client: TestClient) -> None:
    client.post(
        "/api/v1/companies",
        json={"id": "testco2", "name": "TestCo2"},
    )
    a = client.post(
        "/api/v1/companies/testco2/accounts",
        json={"code": "1000", "name": "Cash", "type": "asset"},
    ).json()
    b = client.post(
        "/api/v1/companies/testco2/accounts",
        json={"code": "4000", "name": "Revenue", "type": "income"},
    ).json()
    # Deactivate the cash account.
    resp = client.post(
        f"/api/v1/companies/testco2/accounts/{a['id']}/deactivate"
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # New entry referencing the deactivated account fails.
    resp = client.post(
        "/api/v1/companies/testco2/journal-entries",
        json={
            "entry_date": "2026-01-01",
            "lines": [
                {"account_id": a["id"], "debit_cents": 100},
                {"account_id": b["id"], "credit_cents": 100},
            ],
        },
    )
    assert resp.status_code == 400
    assert "deactivated" in resp.text


def test_path_traversal_rejected(client: TestClient) -> None:
    resp = client.get("/api/v1/companies/..%2Fetc/accounts")
    # FastAPI normalizes %2F to /, which the path router itself sees as a
    # new segment. Either 404 or 400 is acceptable — the key is "not 200".
    assert resp.status_code in (400, 404)
