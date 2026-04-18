"""Profit & loss report tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> dict[str, int]:
    client.post(
        "/api/v1/companies",
        json={"id": "testco", "name": "Test Co."},
    )
    accounts = [
        ("1000", "Cash", "asset"),
        ("4000", "Service Revenue", "income"),
        ("4010", "Consulting Revenue", "income"),
        ("5000", "Rent Expense", "expense"),
        ("5010", "Utilities Expense", "expense"),
    ]
    ids: dict[str, int] = {}
    for code, name, type_ in accounts:
        resp = client.post(
            "/api/v1/companies/testco/accounts",
            json={"code": code, "name": name, "type": type_},
        )
        ids[code] = resp.json()["id"]
    return ids


def _post(client: TestClient, entry_date: str, lines: list[dict]) -> None:
    resp = client.post(
        "/api/v1/companies/testco/journal-entries",
        json={"entry_date": entry_date, "lines": lines},
    )
    assert resp.status_code == 201, resp.text
    entry_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/companies/testco/journal-entries/{entry_id}/post"
    )
    assert resp.status_code == 200, resp.text


def test_pl_basic(client: TestClient) -> None:
    ids = _seed(client)
    # January: earn 1000 service + 500 consulting, spend 200 rent + 100 utilities.
    _post(client, "2026-01-10", [
        {"account_id": ids["1000"], "debit_cents": 100000},
        {"account_id": ids["4000"], "credit_cents": 100000},
    ])
    _post(client, "2026-01-15", [
        {"account_id": ids["1000"], "debit_cents": 50000},
        {"account_id": ids["4010"], "credit_cents": 50000},
    ])
    _post(client, "2026-01-20", [
        {"account_id": ids["5000"], "debit_cents": 20000},
        {"account_id": ids["1000"], "credit_cents": 20000},
    ])
    _post(client, "2026-01-25", [
        {"account_id": ids["5010"], "debit_cents": 10000},
        {"account_id": ids["1000"], "credit_cents": 10000},
    ])

    resp = client.get(
        "/api/v1/companies/testco/reports/profit-loss",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert resp.status_code == 200
    pl = resp.json()
    assert pl["income"]["subtotal_cents"] == 150000
    assert pl["expenses"]["subtotal_cents"] == 30000
    assert pl["net_income_cents"] == 120000
    # Two income rows, two expense rows.
    assert len(pl["income"]["rows"]) == 2
    assert len(pl["expenses"]["rows"]) == 2


def test_pl_windowing(client: TestClient) -> None:
    ids = _seed(client)
    _post(client, "2026-01-15", [
        {"account_id": ids["1000"], "debit_cents": 10000},
        {"account_id": ids["4000"], "credit_cents": 10000},
    ])
    _post(client, "2026-02-15", [
        {"account_id": ids["1000"], "debit_cents": 20000},
        {"account_id": ids["4000"], "credit_cents": 20000},
    ])

    resp = client.get(
        "/api/v1/companies/testco/reports/profit-loss",
        params={"start_date": "2026-02-01", "end_date": "2026-02-28"},
    )
    pl = resp.json()
    assert pl["income"]["subtotal_cents"] == 20000
    assert pl["net_income_cents"] == 20000


def test_pl_prior_period_comparison(client: TestClient) -> None:
    ids = _seed(client)
    _post(client, "2025-12-10", [
        {"account_id": ids["1000"], "debit_cents": 50000},
        {"account_id": ids["4000"], "credit_cents": 50000},
    ])
    _post(client, "2026-01-10", [
        {"account_id": ids["1000"], "debit_cents": 100000},
        {"account_id": ids["4000"], "credit_cents": 100000},
    ])

    resp = client.get(
        "/api/v1/companies/testco/reports/profit-loss",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "compare_prior_period": True,
        },
    )
    pl = resp.json()
    assert pl["income"]["subtotal_cents"] == 100000
    assert pl["income"]["prior_subtotal_cents"] == 50000
    assert pl["net_income_cents"] == 100000
    assert pl["prior_net_income_cents"] == 50000


def test_pl_drafts_excluded(client: TestClient) -> None:
    ids = _seed(client)
    # Posted entry.
    _post(client, "2026-01-10", [
        {"account_id": ids["1000"], "debit_cents": 10000},
        {"account_id": ids["4000"], "credit_cents": 10000},
    ])
    # Draft only — should NOT show up.
    resp = client.post(
        "/api/v1/companies/testco/journal-entries",
        json={
            "entry_date": "2026-01-15",
            "lines": [
                {"account_id": ids["1000"], "debit_cents": 999999},
                {"account_id": ids["4000"], "credit_cents": 999999},
            ],
        },
    )
    assert resp.status_code == 201

    resp = client.get(
        "/api/v1/companies/testco/reports/profit-loss",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    pl = resp.json()
    assert pl["income"]["subtotal_cents"] == 10000
