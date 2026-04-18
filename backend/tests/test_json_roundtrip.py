"""JSON export/import round-trip tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _set_up(client: TestClient) -> dict[str, int]:
    """Create a company with accounts and mixed entries (posted + void)."""
    client.post(
        "/api/v1/companies?template=sched_c_service",
        json={"id": "src", "name": "Source Co."},
    )
    resp = client.get("/api/v1/companies/src/accounts")
    ids = {a["code"]: a["id"] for a in resp.json()}

    # Posted entry.
    e1 = client.post(
        "/api/v1/companies/src/journal-entries",
        json={
            "entry_date": "2026-01-15",
            "reference": "INV-001",
            "memo": "First invoice",
            "lines": [
                {"account_id": ids["1000"], "debit_cents": 10000},
                {"account_id": ids["4000"], "credit_cents": 10000},
            ],
        },
    ).json()
    client.post(f"/api/v1/companies/src/journal-entries/{e1['id']}/post")

    # Another posted entry, then voided.
    e2 = client.post(
        "/api/v1/companies/src/journal-entries",
        json={
            "entry_date": "2026-01-20",
            "reference": "INV-002",
            "lines": [
                {"account_id": ids["1000"], "debit_cents": 5000},
                {"account_id": ids["4000"], "credit_cents": 5000},
            ],
        },
    ).json()
    client.post(f"/api/v1/companies/src/journal-entries/{e2['id']}/post")
    client.post(
        f"/api/v1/companies/src/journal-entries/{e2['id']}/void",
        json={"memo": "test void"},
    )

    return ids


def test_export_returns_complete_document(client: TestClient) -> None:
    _set_up(client)
    resp = client.get("/api/v1/companies/src/export/company.json")
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["ledgerline_export_version"] == 1
    assert doc["company"]["id"] == "src"
    assert len(doc["accounts"]) > 0
    # Two original entries + one reversal = 3.
    assert len(doc["journal_entries"]) == 3
    assert {e["status"] for e in doc["journal_entries"]} == {"posted", "void"}


def test_roundtrip_preserves_register(client: TestClient) -> None:
    ids = _set_up(client)
    cash_id = ids["1000"]

    # Snapshot the source register.
    src_reg = client.get(f"/api/v1/companies/src/accounts/{cash_id}/register").json()

    # Export.
    doc = client.get("/api/v1/companies/src/export/company.json").json()

    # Import under a new id.
    resp = client.post("/api/v1/import/company?override_id=dst", json=doc)
    assert resp.status_code == 201, resp.text

    # Compare registers. Account IDs are preserved, so cash_id is valid in
    # both companies.
    dst_reg = client.get(f"/api/v1/companies/dst/accounts/{cash_id}/register").json()
    assert src_reg["closing_balance_cents"] == dst_reg["closing_balance_cents"]
    assert len(src_reg["rows"]) == len(dst_reg["rows"])


def test_roundtrip_preserves_reports(client: TestClient) -> None:
    _set_up(client)
    doc = client.get("/api/v1/companies/src/export/company.json").json()
    client.post("/api/v1/import/company?override_id=dst", json=doc)

    src_tb = client.get(
        "/api/v1/companies/src/reports/trial-balance",
        params={"as_of_date": "2026-12-31"},
    ).json()
    dst_tb = client.get(
        "/api/v1/companies/dst/reports/trial-balance",
        params={"as_of_date": "2026-12-31"},
    ).json()
    assert src_tb["total_debit_cents"] == dst_tb["total_debit_cents"]
    assert src_tb["total_credit_cents"] == dst_tb["total_credit_cents"]


def test_import_rejects_duplicate_id(client: TestClient) -> None:
    _set_up(client)
    doc = client.get("/api/v1/companies/src/export/company.json").json()
    # Same id would collide with the source company.
    resp = client.post("/api/v1/import/company", json=doc)
    assert resp.status_code == 409


def test_import_rejects_wrong_version(client: TestClient) -> None:
    _set_up(client)
    doc = client.get("/api/v1/companies/src/export/company.json").json()
    doc["ledgerline_export_version"] = 99
    resp = client.post(
        "/api/v1/import/company?override_id=wontgetused", json=doc
    )
    assert resp.status_code == 400
    assert "unsupported export version" in resp.text


def test_import_rejects_invalid_company_id(client: TestClient) -> None:
    _set_up(client)
    doc = client.get("/api/v1/companies/src/export/company.json").json()
    resp = client.post(
        "/api/v1/import/company?override_id=Not%20A%20Slug", json=doc
    )
    assert resp.status_code == 400
