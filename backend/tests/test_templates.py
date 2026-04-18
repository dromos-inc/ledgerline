"""Chart-of-accounts template tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_templates(client: TestClient) -> None:
    resp = client.get("/api/v1/companies/templates")
    assert resp.status_code == 200
    templates = resp.json()
    keys = {t["key"] for t in templates}
    assert {"sched_c_service", "sched_c_retail", "s_corp_general"} <= keys
    for t in templates:
        assert t["account_count"] > 5


def test_create_company_with_template_seeds_coa(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/companies?template=sched_c_service",
        json={"id": "acme", "name": "Acme Services"},
    )
    assert resp.status_code == 201

    resp = client.get("/api/v1/companies/acme/accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    codes = {a["code"] for a in accounts}
    # Spot-check a handful of accounts the service template should have.
    assert "1000" in codes  # Cash
    assert "3000" in codes  # Owner's Equity
    assert "4000" in codes  # Service Revenue
    assert "5000" in codes  # Rent Expense
    # Retail-only accounts should NOT be present.
    assert "1300" not in codes  # Inventory


def test_create_company_with_s_corp_template(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/companies?template=s_corp_general",
        json={"id": "dromos-inc", "name": "Dromos Inc.", "entity_type": "s_corp"},
    )
    assert resp.status_code == 201

    resp = client.get("/api/v1/companies/dromos-inc/accounts")
    accounts = resp.json()
    by_name = {a["name"]: a for a in accounts}
    # S-corp equity structure.
    assert "Common Stock" in by_name
    assert "Additional Paid-In Capital" in by_name
    assert "Shareholder Distributions" in by_name
    assert "Retained Earnings" in by_name


def test_unknown_template_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/companies?template=fortune_500",
        json={"id": "x", "name": "X"},
    )
    assert resp.status_code == 400
    assert "unknown template" in resp.text


def test_company_created_without_template_has_no_accounts(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/companies",
        json={"id": "blank", "name": "Blank Co."},
    )
    assert resp.status_code == 201
    resp = client.get("/api/v1/companies/blank/accounts")
    assert resp.json() == []
