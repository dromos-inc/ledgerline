"""Shared pytest fixtures.

Each test that touches the filesystem gets an isolated temporary
``data_dir`` so tests can run in parallel without stepping on each other.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings with ``data_dir`` pointed at a temp directory."""
    return Settings(data_dir=tmp_path / "ledgerline", dev_mode=True)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """A FastAPI app wired with the test settings."""
    return create_app(settings=settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """HTTP test client. Triggers app lifespan (data dir creation)."""
    with TestClient(app) as c:
        yield c
