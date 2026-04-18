"""Balance sheet report tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> dict[str, int]:
    client.post(
        "/api/v1/companies",
        json={"id": "bsco", "name": "BS Co."},
    )
    accounts = [
        ("1000", "Cash", "asset"),
        ("1500", "Equipment", "asset"),
        ("2000", "Accounts Payable", "liability"),
        ("3000", "Owner's Equity", "equity"),
        ("4000", "Revenue", "income"),
        ("5000", "Expenses", "expense"),
    ]
    ids: dict[str, int] = {}
    for code, name, type_ in accounts:
        resp = client.post(
            "/api/v1/companies/bsco/accounts",
            json={"code": code, "name": name, "type": type_},
        )
        ids[code] = resp.json()["id"]
    return ids


def _post(client: TestClient, entry_date: str, lines: list[dict]) -> None:
    resp = client.post(
        "/api/v1/companies/bsco/journal-entries",
        json={"entry_date": entry_date, "lines": lines},
    )
    entry_id = resp.json()["id"]
    client.post(f"/api/v1/companies/bsco/journal-entries/{entry_id}/post")


def test_balance_sheet_balances_on_equity_contribution(client: TestClient) -> None:
    """Starting equity: owner contributes $5000 cash. Assets=5000, Equity=5000."""
    ids = _seed(client)
    _post(client, "2026-01-01", [
        {"account_id": ids["1000"], "debit_cents": 500000},
        {"account_id": ids["3000"], "credit_cents": 500000},
    ])

    resp = client.get(
        "/api/v1/companies/bsco/reports/balance-sheet",
        params={"as_of_date": "2026-12-31"},
    )
    assert resp.status_code == 200
    bs = resp.json()
    assert bs["balanced"] is True
    assert bs["equation_difference_cents"] == 0
    assert bs["assets"]["subtotal_cents"] == 500000
    assert bs["liabilities"]["subtotal_cents"] == 0
    assert bs["equity"]["subtotal_cents"] == 500000


def test_balance_sheet_with_liabilities(client: TestClient) -> None:
    ids = _seed(client)
    # Buy equipment $3000 on credit. DR Equipment 3000, CR AP 3000.
    _post(client, "2026-01-01", [
        {"account_id": ids["1500"], "debit_cents": 300000},
        {"account_id": ids["2000"], "credit_cents": 300000},
    ])

    resp = client.get(
        "/api/v1/companies/bsco/reports/balance-sheet",
        params={"as_of_date": "2026-12-31"},
    )
    bs = resp.json()
    assert bs["balanced"] is True
    assert bs["assets"]["subtotal_cents"] == 300000
    assert bs["liabilities"]["subtotal_cents"] == 300000
    assert bs["equity"]["subtotal_cents"] == 0


def test_balance_sheet_rolls_current_year_earnings(client: TestClient) -> None:
    """Revenue and expenses show up as Current Year Earnings in Equity.

    DR Cash 10000 / CR Revenue 10000 (earned)
    DR Expenses 3000 / CR Cash 3000 (spent)
    Assets: cash 7000. Equity: CYE 7000. Liabilities: 0. Balances.
    """
    ids = _seed(client)
    _post(client, "2026-01-10", [
        {"account_id": ids["1000"], "debit_cents": 1000000},
        {"account_id": ids["4000"], "credit_cents": 1000000},
    ])
    _post(client, "2026-01-20", [
        {"account_id": ids["5000"], "debit_cents": 300000},
        {"account_id": ids["1000"], "credit_cents": 300000},
    ])

    resp = client.get(
        "/api/v1/companies/bsco/reports/balance-sheet",
        params={"as_of_date": "2026-12-31"},
    )
    bs = resp.json()
    assert bs["balanced"] is True
    assert bs["assets"]["subtotal_cents"] == 700000
    assert bs["equity"]["subtotal_cents"] == 700000
    # Current Year Earnings row present.
    cye_rows = [r for r in bs["equity"]["rows"] if r["account_name"] == "Current Year Earnings"]
    assert len(cye_rows) == 1
    assert cye_rows[0]["balance_cents"] == 700000


def test_balance_sheet_income_expense_accounts_not_in_sections(client: TestClient) -> None:
    """Income and Expense accounts roll into CYE; they don't appear as
    sections themselves."""
    ids = _seed(client)
    _post(client, "2026-01-10", [
        {"account_id": ids["1000"], "debit_cents": 1000000},
        {"account_id": ids["4000"], "credit_cents": 1000000},
    ])

    resp = client.get(
        "/api/v1/companies/bsco/reports/balance-sheet",
        params={"as_of_date": "2026-12-31"},
    )
    bs = resp.json()
    all_rows = (
        bs["assets"]["rows"] + bs["liabilities"]["rows"] + bs["equity"]["rows"]
    )
    codes = {row["account_code"] for row in all_rows}
    assert "4000" not in codes  # income
    assert "5000" not in codes  # expense
    assert "1000" in codes  # cash
