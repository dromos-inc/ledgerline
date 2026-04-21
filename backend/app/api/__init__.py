"""FastAPI routers.

Each module defines a single APIRouter and attaches it in
``app.api.register_routers``. Keeping routers grouped by domain makes
the OpenAPI spec self-organising.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from app.api import (
    accounts,
    companies,
    customers,
    export,
    import_api,
    invoices,
    journal,
    payments,
    register,
    reports,
    vendors,
)


def register_routers(app: FastAPI, *, prefix: str) -> None:
    """Mount all API routers under ``prefix`` (e.g. ``/api/v1``)."""
    api = APIRouter(prefix=prefix)
    api.include_router(companies.router)
    api.include_router(accounts.router)
    api.include_router(customers.router)
    api.include_router(vendors.router)
    api.include_router(invoices.router)
    api.include_router(payments.router)
    api.include_router(journal.router)
    api.include_router(register.router)
    api.include_router(reports.router)
    api.include_router(export.router)
    api.include_router(import_api.router)
    app.include_router(api)
