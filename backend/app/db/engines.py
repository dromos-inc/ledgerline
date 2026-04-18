"""SQLAlchemy engine construction and caching.

Engines are lightweight but carry connection pools and dialect state.
We cache them per-path so that repeatedly opening the same company
database doesn't open a new pool each time.

SQLite PRAGMAs enforced on every connection:

- ``foreign_keys=ON``   — required for FK constraints to be checked.
- ``journal_mode=WAL``  — faster concurrent reads, cheap to enable.
- ``synchronous=NORMAL``— durable enough for accounting, much faster
                          than the default ``FULL``.
- ``busy_timeout=5000`` — wait up to 5s for a lock before failing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection

from app.config import Settings

logger = logging.getLogger(__name__)

_company_engines: dict[str, Engine] = {}
_company_engines_lock = Lock()

_registry_engine: Engine | None = None
_registry_engine_lock = Lock()


def _apply_pragmas(dbapi_connection: DBAPIConnection, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
    finally:
        cursor.close()


def _make_engine(db_path: Path, *, echo: bool = False) -> Engine:
    """Create a SQLite engine bound to ``db_path`` with standard PRAGMAs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(
        url,
        echo=echo,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 5.0},
    )
    event.listen(engine, "connect", _apply_pragmas)
    return engine


def registry_engine(settings: Settings) -> Engine:
    """Return the cached registry engine, creating it on first call."""
    global _registry_engine
    if _registry_engine is not None:
        return _registry_engine
    with _registry_engine_lock:
        if _registry_engine is None:
            settings.ensure_directories()
            _registry_engine = _make_engine(settings.registry_db_path(), echo=settings.dev_mode)
            logger.info("Registry engine created at %s", settings.registry_db_path())
    return _registry_engine


def company_engine(settings: Settings, company_id: str) -> Engine:
    """Return a cached engine for the given company id."""
    cached = _company_engines.get(company_id)
    if cached is not None:
        return cached
    with _company_engines_lock:
        cached = _company_engines.get(company_id)
        if cached is None:
            settings.ensure_directories()
            path = settings.company_db_path(company_id)
            cached = _make_engine(path, echo=settings.dev_mode)
            _company_engines[company_id] = cached
            logger.info("Company engine created for %s at %s", company_id, path)
    return cached


def dispose_company_engines() -> None:
    """Dispose every cached company engine. Useful for tests."""
    global _registry_engine
    with _company_engines_lock:
        for engine in _company_engines.values():
            engine.dispose()
        _company_engines.clear()
    with _registry_engine_lock:
        if _registry_engine is not None:
            _registry_engine.dispose()
            _registry_engine = None
