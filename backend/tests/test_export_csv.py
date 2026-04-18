"""CSV export tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> dict[str, int]:
    client.post(
        "/api/v1/companies?template=sched_c_service",
        json={"id": "exco", "name": "Exco"},
    )
    resp = client.get("/api/v1/companies/exco/accounts")
    ids = {a["code"]: a["id"] for a in resp.json()}

    # Post one entry so reports have content.
    e = client.post(
        "/api/v1/companies/exco/journal-entries",
        json={
            "entry_date": "2026-01-15",
            "reference": "TEST-1",
            "memo": "Test entry",
            "lines": [
                {"account_id": ids["1000"], "debit_cents": 10000},
                {"account_id": ids["4000"], "credit_cents": 10000},
            ],
        },
    ).json()
    client.post(f"/api/v1/companies/exco/journal-entries/{e['id']}/post")
    return ids


def test_accounts_csv(client: TestClient) -> None:
    _seed(client)
    resp = client.get("/api/v1/companies/exco/export/accounts.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "accounts.csv" in resp.headers["content-disposition"]
    body = resp.text
    assert body.startswith("code,name,type")
    assert "1000,Cash,asset" in body


def test_journal_entries_csv(client: TestClient) -> None:
    _seed(client)
    resp = client.get("/api/v1/companies/exco/export/journal-entries.csv")
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("entry_id,entry_date,posting_date")
    # Two lines per entry.
    lines = body.strip().split("\n")
    assert len(lines) == 3  # header + 2 lines


def test_register_csv(client: TestClient) -> None:
    ids = _seed(client)
    cash_id = ids["1000"]
    resp = client.get(
        f"/api/v1/companies/exco/export/register.csv?account_id={cash_id}"
    )
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("entry_date,posting_date")
    assert "register-1000.csv" in resp.headers["content-disposition"]


def test_trial_balance_csv(client: TestClient) -> None:
    _seed(client)
    resp = client.get(
        "/api/v1/companies/exco/export/reports/trial-balance.csv?as_of_date=2026-12-31"
    )
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("code,name,type,debit,credit")
    assert "TOTAL" in body


def test_profit_loss_csv(client: TestClient) -> None:
    _seed(client)
    resp = client.get(
        "/api/v1/companies/exco/export/reports/profit-loss.csv"
        "?start_date=2026-01-01&end_date=2026-12-31"
    )
    assert resp.status_code == 200
    body = resp.text
    assert "section,code,name,amount" in body
    assert "Net Income" in body


def test_balance_sheet_csv(client: TestClient) -> None:
    _seed(client)
    resp = client.get(
        "/api/v1/companies/exco/export/reports/balance-sheet.csv?as_of_date=2026-12-31"
    )
    assert resp.status_code == 200
    body = resp.text
    assert "section,code,name,balance" in body
    assert "Total Assets" in body


def test_cents_to_dollars_formatting(client: TestClient) -> None:
    from app.export.csv import cents_to_dollars

    assert cents_to_dollars(0) == "0.00"
    assert cents_to_dollars(1) == "0.01"
    assert cents_to_dollars(100) == "1.00"
    assert cents_to_dollars(123456) == "1234.56"
    assert cents_to_dollars(-500) == "-5.00"
