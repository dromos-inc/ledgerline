"""Liveness endpoint — trivial but catches boot-time regressions."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_root_serves_landing_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Ledgerline API" in response.text
    assert "/docs" in response.text


def test_openapi_schema_published(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Ledgerline API"
    assert "/health" in schema["paths"]
