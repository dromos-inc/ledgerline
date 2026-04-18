"""Exercise the DB layer: engine caching, PRAGMAs, session semantics."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.config import Settings
from app.db.engines import (
    company_engine,
    dispose_company_engines,
    registry_engine,
)
from app.db.session import company_session, registry_session


@pytest.fixture(autouse=True)
def _dispose() -> None:
    dispose_company_engines()
    yield
    dispose_company_engines()


def test_registry_engine_is_cached(settings: Settings) -> None:
    a = registry_engine(settings)
    b = registry_engine(settings)
    assert a is b


def test_company_engine_is_cached_per_id(settings: Settings) -> None:
    a = company_engine(settings, "acme")
    b = company_engine(settings, "acme")
    c = company_engine(settings, "globex")
    assert a is b
    assert a is not c


def test_sqlite_pragmas_applied(settings: Settings) -> None:
    engine = company_engine(settings, "acme")
    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar_one()
        journal = conn.execute(text("PRAGMA journal_mode")).scalar_one()
    assert fk == 1
    assert journal.lower() == "wal"


def test_company_session_creates_file(settings: Settings) -> None:
    path = settings.company_db_path("newco")
    assert not path.exists()
    with company_session("newco", settings) as session:
        session.execute(text("SELECT 1"))
    assert path.exists()


def test_company_db_paths_isolated(settings: Settings, tmp_path: Path) -> None:
    assert settings.data_dir == tmp_path / "ledgerline"
    a_path = settings.company_db_path("a")
    b_path = settings.company_db_path("b")
    assert a_path != b_path
    assert a_path.parent == b_path.parent


def test_registry_session_commits_on_exit(settings: Settings) -> None:
    with registry_session(settings) as session:
        session.execute(
            text("CREATE TABLE IF NOT EXISTS smoke (id INTEGER PRIMARY KEY, v TEXT)")
        )
        session.execute(text("INSERT INTO smoke (v) VALUES ('hello')"))

    with registry_session(settings) as session:
        value = session.execute(text("SELECT v FROM smoke")).scalar_one()
    assert value == "hello"
