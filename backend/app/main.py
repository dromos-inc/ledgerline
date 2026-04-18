"""FastAPI application entry point.

Exposes:
- ``GET /health``  — liveness probe used by Electron to wait for the
                     backend to become ready before loading the UI.
- ``GET /``        — tiny landing page that points visitors at ``/docs``.
- ``GET /docs``    — FastAPI-generated OpenAPI Swagger UI.
- ``GET /openapi.json`` — machine-readable OpenAPI 3.x specification.
- API routers mounted under ``settings.api_prefix`` (default ``/api/v1``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app import __version__
from app.api import register_routers
from app.config import Settings, get_settings
from app.db.engines import registry_engine
from app.db.schema import ensure_registry_schema


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: ensure data directories + registry schema exist."""
    settings: Settings = app.state.settings
    settings.ensure_directories()
    engine = registry_engine(settings)
    ensure_registry_schema(engine)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Takes settings for testability."""
    settings = settings or get_settings()
    app = FastAPI(
        title="Ledgerline API",
        description=(
            "Double-entry accounting platform. This API is the same across "
            "local, cloud, and self-hosted tiers."
        ),
        version=__version__,
        lifespan=_lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routers(app, prefix=settings.api_prefix)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe. Always returns {\"status\": \"ok\"} once bound."""
        return {"status": "ok", "version": __version__}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> str:
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Ledgerline API</title></head><body style='font-family:ui-monospace,monospace;"
            "max-width:40rem;margin:2rem auto;padding:0 1rem;line-height:1.5'>"
            "<h1>Ledgerline API</h1>"
            f"<p>Version {__version__}. API documentation at "
            "<a href='/docs'>/docs</a>. OpenAPI spec at "
            "<a href='/openapi.json'>/openapi.json</a>.</p></body></html>"
        )

    return app


app = create_app()


def run() -> None:
    """Entry point for ``ledgerline-api`` console script and Electron."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.dev_mode,
    )


if __name__ == "__main__":
    run()
