"""Report correctness tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_dromos(client: TestClient) -> dict[str, int]:
    """Set up a company with a small CoA and two posted entries."""
    client.post(
        "/api/v1/companies",
        json={"id": "dromos-inc", "name": "Dromos Inc.", "tax_basis": "accrual"},
    )
    accounts = [
        ("1000", "Cash", "asset"),
        ("4000", "Service Revenue", "income"),
        ("5000", "Rent Expense", "expense"),
    ]
    ids: dict[str, int] = {}
    for code, name, type_ in accounts:
        resp = client.post(
            "/api/v1/companies/dromos-inc/accounts",
            json={"code": code, "name": name, "type": type_},
        )
        ids[code] = resp.json()["id"]

    # Revenue entry: +100 to cash, +100 income.
    e1 = client.post(
        "/api/v1/companies/dromos-inc/journal-entries",
        json={
            "entry_date": "2026-01-15",
            "lines": [
                {"account_id": ids["1000"], "debit_cents": 10000},
                {"account_id": ids["4000"], "credit_cents": 10000},
            ],
        },
    ).json()
    client.post(
        f"/api/v1/companies/dromos-inc/journal-entries/{e1['id']}/post"
    )

    # Expense entry: pay rent $30.
    e2 = client.post(
        "/api/v1/companies/dromos-inc/journal-entries",
        json={
            "entry_date": "2026-01-31",
            "lines": [
                {"account_id": ids["5000"], "debit_cents": 3000},
                {"account_id": ids["1000"], "credit_cents": 3000},
            ],
        },
    ).json()
    client.post(
        f"/api/v1/companies/dromos-inc/journal-entries/{e2['id']}/post"
    )
    return ids


def test_trial_balance_balances(client: TestClient) -> None:
    _seed_dromos(client)

    resp = client.get(
        "/api/v1/companies/dromos-inc/reports/trial-balance",
        params={"as_of_date": "2026-12-31"},
    )
    assert resp.status_code == 200
    tb = resp.json()
    assert tb["balanced"] is True
    assert tb["total_debit_cents"] == tb["total_credit_cents"]

    by_code = {row["account_code"]: row for row in tb["rows"]}
    assert by_code["1000"]["debit_cents"] == 7000  # cash 100 - 30
    assert by_code["1000"]["credit_cents"] == 0
    assert by_code["4000"]["credit_cents"] == 10000  # revenue 100
    assert by_code["4000"]["debit_cents"] == 0
    assert by_code["5000"]["debit_cents"] == 3000  # rent 30


def test_trial_balance_respects_as_of_date(client: TestClient) -> None:
    _seed_dromos(client)

    # As of mid-month: only the revenue entry counts.
    resp = client.get(
        "/api/v1/companies/dromos-inc/reports/trial-balance",
        params={"as_of_date": "2026-01-20"},
    )
    tb = resp.json()
    by_code = {row["account_code"]: row for row in tb["rows"]}
    assert by_code["1000"]["debit_cents"] == 10000
    # Rent entry on 01-31 excluded.
    assert "5000" not in by_code


def test_trial_balance_excludes_zero_balance_by_default(client: TestClient) -> None:
    _seed_dromos(client)

    # Before any activity: empty trial balance.
    resp = client.get(
        "/api/v1/companies/dromos-inc/reports/trial-balance",
        params={"as_of_date": "2025-12-31"},
    )
    assert resp.json()["rows"] == []


def test_trial_balance_excludes_drafts(client: TestClient) -> None:
    ids = _seed_dromos(client)

    # Draft entry never contributes.
    resp = client.post(
        "/api/v1/companies/dromos-inc/journal-entries",
        json={
            "entry_date": "2026-06-01",
            "lines": [
                {"account_id": ids["1000"], "debit_cents": 50000},
                {"account_id": ids["4000"], "credit_cents": 50000},
            ],
        },
    )
    assert resp.status_code == 201
    # Do NOT post it.

    resp = client.get(
        "/api/v1/companies/dromos-inc/reports/trial-balance",
        params={"as_of_date": "2026-12-31"},
    )
    by_code = {row["account_code"]: row for row in resp.json()["rows"]}
    # Cash is still +7000 (not +57000) because the draft doesn't count.
    assert by_code["1000"]["debit_cents"] == 7000
