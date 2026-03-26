"""Test-level pytest fixtures — in-memory SQLite session for DB tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide a fresh in-memory SQLite session per test.

    Phase 2 will import Base from db.models and call create_all here.
    For Phase 1 this fixture is a placeholder that ensures the test
    infrastructure runs without errors.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
