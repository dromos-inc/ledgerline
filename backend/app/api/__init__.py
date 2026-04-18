"""FastAPI routers.

Each module defines a single APIRouter and attaches it in
``app.api.register_routers``. Keeping routers grouped by domain makes
the OpenAPI spec self-organising.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from app.api import companies


def register_routers(app: FastAPI, *, prefix: str) -> None:
    """Mount all API routers under ``prefix`` (e.g. ``/api/v1``)."""
    api = APIRouter(prefix=prefix)
    api.include_router(companies.router)
    app.include_router(api)
