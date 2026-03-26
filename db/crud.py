"""Async CRUD operations for EdgeDesk database models.

All functions accept an `AsyncSession` — callers are responsible for
acquiring it via `get_session()` and committing/rolling back as needed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemoryRecord, Execution, Rule, _utcnow_iso

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


async def create_rule(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    trigger_type: str | None = None,
    trigger_config: dict[str, Any] | None = None,
    steps: list[Any] | None = None,
    enabled: bool = True,
) -> Rule:
    """Insert and return a new Rule."""
    rule = Rule(
        name=name,
        description=description,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        steps=steps,
        enabled=enabled,
    )
    session.add(rule)
    await session.flush()
    return rule


async def get_rule(session: AsyncSession, rule_id: str) -> Rule | None:
    """Fetch a rule by primary key. Returns None if not found."""
    result = await session.execute(select(Rule).where(Rule.id == rule_id))
    return result.scalar_one_or_none()


async def get_rule_by_name(session: AsyncSession, name: str) -> Rule | None:
    """Fetch a rule by unique name."""
    result = await session.execute(select(Rule).where(Rule.name == name))
    return result.scalar_one_or_none()


async def list_rules(
    session: AsyncSession,
    *,
    enabled_only: bool = False,
) -> list[Rule]:
    """Return all rules, optionally filtered to enabled ones."""
    stmt = select(Rule)
    if enabled_only:
        stmt = stmt.where(Rule.enabled.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_rule(
    session: AsyncSession,
    rule_id: str,
    **kwargs: Any,
) -> Rule | None:
    """Partial-update a rule by ID. Returns updated rule or None."""
    rule = await get_rule(session, rule_id)
    if rule is None:
        return None
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = _utcnow_iso()
    await session.flush()
    return rule


async def delete_rule(session: AsyncSession, rule_id: str) -> bool:
    """Delete a rule by ID. Returns True if deleted, False if not found."""
    rule = await get_rule(session, rule_id)
    if rule is None:
        return False
    await session.delete(rule)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Executions
# ---------------------------------------------------------------------------


async def create_execution(
    session: AsyncSession,
    *,
    instruction: str,
    rule_id: str | None = None,
    steps_log: list[Any] | None = None,
    status: str = "success",
    duration_ms: int | None = None,
) -> Execution:
    """Insert and return a new Execution record."""
    execution = Execution(
        rule_id=rule_id,
        instruction=instruction,
        steps_log=steps_log or [],
        status=status,
        duration_ms=duration_ms,
    )
    session.add(execution)
    await session.flush()
    return execution


async def list_executions(
    session: AsyncSession,
    *,
    rule_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Execution]:
    """Return executions, newest first. Optionally filtered by rule_id."""
    stmt = select(Execution).order_by(Execution.executed_at.desc()).limit(limit).offset(offset)
    if rule_id is not None:
        stmt = stmt.where(Execution.rule_id == rule_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_feedback(
    session: AsyncSession,
    execution_id: str,
    feedback: int,
) -> Execution | None:
    """Set feedback (1=good, -1=bad, 0=none) on an execution."""
    result = await session.execute(
        select(Execution).where(Execution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        return None
    execution.feedback = feedback
    await session.flush()
    return execution


# ---------------------------------------------------------------------------
# Agent Memory
# ---------------------------------------------------------------------------


async def upsert_memory(
    session: AsyncSession,
    session_id: str,
    summary: str,
) -> AgentMemoryRecord:
    """Create or update the memory summary for a session."""
    result = await session.execute(
        select(AgentMemoryRecord).where(AgentMemoryRecord.session_id == session_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = AgentMemoryRecord(session_id=session_id, summary=summary)
        session.add(record)
    else:
        record.summary = summary
        record.updated_at = _utcnow_iso()
    await session.flush()
    return record


async def get_memory(session: AsyncSession, session_id: str) -> AgentMemoryRecord | None:
    """Retrieve the memory record for a session."""
    result = await session.execute(
        select(AgentMemoryRecord).where(AgentMemoryRecord.session_id == session_id)
    )
    return result.scalar_one_or_none()
