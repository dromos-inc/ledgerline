"""Session factories and FastAPI dependencies.

Two patterns are exposed:

- Context managers (``registry_session``, ``company_session``) for use in
  services, scripts, and tests.
- FastAPI dependencies (``get_registry_session``, ``get_company_session``)
  for route handlers. The company dependency resolves the company id from
  the URL path parameter.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends, HTTPException, Path, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.engines import company_engine, registry_engine


@contextmanager
def registry_session(settings: Settings | None = None) -> Iterator[Session]:
    """Yield a SQLAlchemy session bound to the registry database."""
    settings = settings or get_settings()
    engine = registry_engine(settings)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def company_session(company_id: str, settings: Settings | None = None) -> Iterator[Session]:
    """Yield a SQLAlchemy session bound to a given company's database."""
    settings = settings or get_settings()
    engine = company_engine(settings, company_id)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- FastAPI dependencies ---------------------------------------------------


def _settings_from_request(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_registry_session(
    request: Request,
) -> Iterator[Session]:
    """FastAPI dependency: yields a registry session."""
    settings = _settings_from_request(request)
    with registry_session(settings) as session:
        yield session


def get_company_session(
    request: Request,
    company_id: str = Path(..., description="Company id from URL."),
) -> Iterator[Session]:
    """FastAPI dependency: yields a session for the company named in the URL."""
    settings = _settings_from_request(request)
    # Guard against path traversal in the company id.
    if not company_id or "/" in company_id or ".." in company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid company_id",
        )
    with company_session(company_id, settings) as session:
        yield session


# Re-export for type-safe imports in routers.
RegistrySession = Depends(get_registry_session)
CompanySession = Depends(get_company_session)
