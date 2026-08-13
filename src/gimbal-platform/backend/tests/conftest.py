"""Pytest configuration: per-test isolated DB + ASGI client fixture.

The spec-1 tests share an ``AsyncClient``-per-test instance but the ``engine``
in :mod:`app.core.db` is module-global and points at ``./data/app.db``.  Without
isolation, consecutive tests in the same ``pytest`` invocation will collide on
unique-username and similar constraints.

This conftest swaps ``app.core.db.engine`` and ``SessionLocal`` for a per-test
in-memory-style SQLite engine (backed by a tempfile in ``tmp_path`` so the
file is cleaned up automatically) and runs ``Base.metadata.create_all`` to
provision the schema before each test.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import models  # noqa: F401  register all models on Base.metadata
from app.models import AuthSession  # noqa: F401  explicit re-export to register table
from app.core import db as db_module
from app.core.db import Base
from app.main import create_app

logger = logging.getLogger(__name__)


@pytest.fixture
async def fresh_db(monkeypatch, tmp_path) -> AsyncGenerator[None, None]:
    """Swap the global DB engine for a per-test SQLite file + create schema."""
    db_file = tmp_path / "test.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        echo=False,
        future=True,
    )
    test_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    monkeypatch.setattr(db_module, "engine", test_engine, raising=True)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_factory, raising=True)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        await test_engine.dispose()


@pytest.fixture(autouse=True)
def _isolate_favorites(tmp_path, monkeypatch):
    """Point the in-memory favorites store at the per-test tmp dir.

    Without this, favorites written by one test pollute the next test in the
    same pytest run (and any local ``data/favorites.json`` from prior runs).
    """
    from app.routers import cases as cases_router
    from app.services import stars_store

    monkeypatch.setattr(cases_router, "_FAV_PATH", tmp_path / "favorites.json")
    cases_router._FAVORITES.clear()
    stars_store.clear_for_tests()
    yield
    cases_router._FAVORITES.clear()
    stars_store.clear_for_tests()


@pytest.fixture
async def client(fresh_db) -> AsyncGenerator[AsyncClient, None]:
    """ASGI test client wired to a freshly-built FastAPI app.

    ``ASGITransport`` does not trigger lifespan by default; the schema is
    already provisioned by ``fresh_db`` so the app can serve requests
    immediately.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
