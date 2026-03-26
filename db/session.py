"""Async SQLAlchemy engine and session factory for EdgeDesk.

Creates the ~/.edgedesk/ data directory and all tables on first call to
`init_db()`. Use `get_session()` as an async context manager for all DB ops.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from db.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _data_dir() -> Path:
    """Resolve the EdgeDesk data directory from env or default."""
    raw = os.environ.get("DATA_DIR", "~/.edgedesk")
    return Path(raw).expanduser().resolve()


def _db_url() -> str:
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{data_dir / 'edgedesk.db'}"


def get_engine(url: str | None = None) -> AsyncEngine:
    """Return (and cache) the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        db_url = url or _db_url()
        _engine = create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in db_url else None,
        )
        logger.debug("DB engine created: {}", db_url)
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return (and cache) the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            engine or get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Create all tables. Call once at application startup."""
    eng = engine or get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def reset_engine() -> None:
    """Reset cached engine and factory (for tests)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
