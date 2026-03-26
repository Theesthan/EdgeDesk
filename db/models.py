"""SQLAlchemy 2.x ORM models for EdgeDesk.

Tables: rules, executions, agent_memory.
All timestamps stored as UTC ISO-8601 strings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all models."""


def _utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _new_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


class Rule(Base):
    """An automation rule — triggered by cron, file event, or manually."""

    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # time_cron | file_event | manual
    trigger_type: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    steps: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)


class Execution(Base):
    """A single agent execution log entry."""

    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    # Soft FK — rules may be deleted while history is kept
    rule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_log: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    # success | partial | failed
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    # 1=good, -1=bad, 0=none
    feedback: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    executed_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)


class AgentMemoryRecord(Base):
    """Persisted conversation summary for the ReAct agent."""

    __tablename__ = "agent_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)
