"""Integration tests for the EdgeDesk Phase 9 boot pipeline.

Tests exercise the non-UI data path:
  instruction → AgentOrchestrator.run() → Execution record in DB

UI-dependent tests are skipped automatically when no display is available.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.models import Base

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sf():
    """In-memory SQLite session factory for integration tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------


class _MockOrchestrator:
    """Yields a fixed list of tokens then finishes."""

    def __init__(self, tokens: list[str] | None = None) -> None:
        self._tokens = tokens or ["Hello", " World"]
        self._llm = None  # required by _run_instruction planner lookup
        self._tools: list = []  # required for tool_names_str
        self.calls: list[str] = []
        self.thread_ids: list[str] = []

    async def run(
        self, instruction: str, thread_id: str | None = None
    ) -> AsyncIterator[str]:
        self.calls.append(instruction)
        self.thread_ids.append(thread_id or "")
        for token in self._tokens:
            yield token


class _ErrorOrchestrator:
    """Raises RuntimeError on first iteration."""

    _llm = None
    _tools: list = []

    async def run(
        self, instruction: str, thread_id: str | None = None
    ) -> AsyncIterator[str]:
        raise RuntimeError("Mock LLM error")
        yield  # pragma: no cover — makes this an async generator


class _MockOverlay:
    """Records calls to on_token / on_step_update."""

    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.steps: list[tuple[str, str, str]] = []

    def on_token(self, token: str) -> None:
        self.tokens.append(token)

    def on_step_update(self, step_id: str, status: str, text: str) -> None:
        self.steps.append((step_id, status, text))


class _MockScheduler:
    """Silently accepts reload_rule() calls."""

    def __init__(self) -> None:
        self.reloaded: list[str] = []

    async def reload_rule(self, rule_id: str) -> None:
        self.reloaded.append(rule_id)


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------


async def test_init_db_creates_tables(tmp_path: Path) -> None:
    """init_db() must create rules, executions, and agent_memory tables."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db.session import init_db

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await init_db(engine)

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in result.fetchall()}

    await engine.dispose()
    assert "rules" in tables
    assert "executions" in tables
    assert "agent_memory" in tables


# ---------------------------------------------------------------------------
# _run_instruction
# ---------------------------------------------------------------------------


async def test_run_instruction_success(sf) -> None:
    """A successful run should create an Execution record with status 'success'."""
    from unittest.mock import patch

    from db.crud import list_executions
    from main import _run_instruction

    overlay = _MockOverlay()
    orch = _MockOrchestrator(["tok1", "tok2"])

    with patch("tools.screen.capture_screen_text", return_value="Desktop"):
        await _run_instruction("open browser", overlay, orch, sf)

    async with sf() as session:
        execs = await list_executions(session)

    assert len(execs) == 1
    assert execs[0].instruction == "open browser"
    assert execs[0].status == "success"
    assert execs[0].duration_ms is not None and execs[0].duration_ms >= 0


async def test_run_instruction_tokens_reach_overlay(sf) -> None:
    """Tokens yielded by the orchestrator must be forwarded to overlay.on_token."""
    from unittest.mock import patch

    from main import _run_instruction

    overlay = _MockOverlay()
    orch = _MockOrchestrator(["alpha", "beta"])

    with patch("tools.screen.capture_screen_text", return_value="Desktop"):
        await _run_instruction("do something", overlay, orch, sf)

    assert overlay.tokens == ["alpha", "beta"]


async def test_run_instruction_failure_logs_failed_status(sf) -> None:
    """An orchestrator that raises should log status 'failed'."""
    from unittest.mock import patch

    from db.crud import list_executions
    from main import _run_instruction

    overlay = _MockOverlay()

    with patch("tools.screen.capture_screen_text", return_value="Desktop"):
        await _run_instruction("bad task", overlay, _ErrorOrchestrator(), sf)

    async with sf() as session:
        execs = await list_executions(session)

    assert len(execs) == 1
    assert execs[0].status == "failed"


async def test_run_instruction_step_updates_sent(sf) -> None:
    """overlay.on_step_update must be called at least for 'running' and final state."""
    from unittest.mock import patch

    from main import _run_instruction

    overlay = _MockOverlay()
    orch = _MockOrchestrator(["x"])

    with patch("tools.screen.capture_screen_text", return_value="Desktop"):
        await _run_instruction("task", overlay, orch, sf)

    statuses = [s for _, s, _ in overlay.steps]
    assert "running" in statuses
    # Final state is 'done' on success
    assert statuses[-1] in {"done", "failed"}


# ---------------------------------------------------------------------------
# _on_rule_saved / _on_rule_deleted / _on_rule_toggled
# ---------------------------------------------------------------------------


async def test_on_rule_saved_new_rule_inserts(sf) -> None:
    """Saving a rule without id should INSERT a new record."""
    from db.crud import list_rules
    from main import _on_rule_saved

    await _on_rule_saved(
        {
            "id": None,
            "name": "New Rule",
            "instruction": "Do something",
            "trigger_type": "manual",
            "trigger_config": {},
        },
        sf,
        _MockScheduler(),
        None,
    )

    async with sf() as session:
        rules = await list_rules(session)

    assert len(rules) == 1
    assert rules[0].name == "New Rule"


async def test_on_rule_saved_existing_rule_updates(sf) -> None:
    """Saving with an existing id should UPDATE the record."""
    from db.crud import create_rule, get_rule
    from main import _on_rule_saved

    async with sf() as session:
        rule = await create_rule(session, name="Old", instruction="x")
        await session.commit()
        rule_id = rule.id

    sched = _MockScheduler()
    await _on_rule_saved(
        {
            "id": rule_id,
            "name": "Updated",
            "instruction": "new task",
            "trigger_type": "manual",
            "trigger_config": {},
        },
        sf,
        sched,
        None,
    )

    async with sf() as session:
        updated = await get_rule(session, rule_id)

    assert updated is not None
    assert updated.name == "Updated"
    assert sched.reloaded == [rule_id]


async def test_on_rule_saved_calls_scheduler_reload(sf) -> None:
    """scheduler.reload_rule() must be called after saving a new rule."""
    from main import _on_rule_saved

    sched = _MockScheduler()
    await _on_rule_saved(
        {
            "id": None,
            "name": "R",
            "instruction": "i",
            "trigger_type": "manual",
            "trigger_config": {},
        },
        sf,
        sched,
        None,
    )

    assert len(sched.reloaded) == 1


async def test_on_rule_deleted_removes_record(sf) -> None:
    """Deleting a rule should remove it from the database."""
    from db.crud import create_rule, list_rules
    from main import _on_rule_deleted

    async with sf() as session:
        rule = await create_rule(session, name="ToDelete", instruction="x")
        await session.commit()
        rule_id = rule.id

    await _on_rule_deleted(rule_id, sf, _MockScheduler())

    async with sf() as session:
        rules = await list_rules(session)

    assert len(rules) == 0


async def test_on_rule_toggled_updates_enabled(sf) -> None:
    """Toggling a rule should update its enabled field."""
    from db.crud import create_rule, get_rule
    from main import _on_rule_toggled

    async with sf() as session:
        rule = await create_rule(session, name="Toggle", instruction="x", enabled=True)
        await session.commit()
        rule_id = rule.id

    await _on_rule_toggled(rule_id, False, sf, _MockScheduler())

    async with sf() as session:
        fetched = await get_rule(session, rule_id)

    assert fetched is not None
    assert fetched.enabled is False


async def test_on_rule_toggled_scheduler_reload(sf) -> None:
    """scheduler.reload_rule() must be called on toggle."""
    from db.crud import create_rule
    from main import _on_rule_toggled

    async with sf() as session:
        rule = await create_rule(session, name="R2", instruction="x")
        await session.commit()
        rule_id = rule.id

    sched = _MockScheduler()
    await _on_rule_toggled(rule_id, True, sf, sched)

    assert rule_id in sched.reloaded


# ---------------------------------------------------------------------------
# _on_feedback
# ---------------------------------------------------------------------------


async def test_on_feedback_records_score(sf) -> None:
    """Feedback should persist the score on the Execution record."""
    from db.crud import create_execution, list_executions
    from main import _on_feedback

    async with sf() as session:
        ex = await create_execution(session, instruction="test")
        await session.commit()
        exec_id = ex.id

    await _on_feedback(exec_id, 1, sf)

    async with sf() as session:
        execs = await list_executions(session)

    assert execs[0].feedback == 1


async def test_on_feedback_negative_score(sf) -> None:
    """A thumbs-down (score=-1) must be persisted correctly."""
    from db.crud import create_execution, list_executions
    from main import _on_feedback

    async with sf() as session:
        ex = await create_execution(session, instruction="x")
        await session.commit()
        exec_id = ex.id

    await _on_feedback(exec_id, -1, sf)

    async with sf() as session:
        execs = await list_executions(session)

    assert execs[0].feedback == -1


# ---------------------------------------------------------------------------
# _clear_history
# ---------------------------------------------------------------------------


async def test_clear_history_removes_all_executions(sf) -> None:
    """_clear_history() should delete all Execution rows."""
    from db.crud import create_execution, list_executions
    from main import _clear_history

    async with sf() as session:
        await create_execution(session, instruction="a")
        await create_execution(session, instruction="b")
        await session.commit()

    await _clear_history(sf)

    async with sf() as session:
        execs = await list_executions(session)

    assert execs == []


# ---------------------------------------------------------------------------
# Ollama health check
# ---------------------------------------------------------------------------


async def test_ollama_health_check_raises_on_unreachable() -> None:
    """health_check() must raise ConnectionError when Ollama is not running."""
    from core.llm import health_check

    with pytest.raises(ConnectionError):
        await health_check(base_url="http://localhost:19997")


# ---------------------------------------------------------------------------
# Smoke test — main module import
# ---------------------------------------------------------------------------


def test_main_importable() -> None:
    """main module must import without errors (no side-effects at import time)."""
    import importlib

    import main as m

    importlib.reload(m)  # ensure idempotent


def test_async_helpers_are_coroutines() -> None:
    """Key async functions must be coroutine functions (not plain functions)."""
    import asyncio

    from main import (
        _clear_history,
        _on_feedback,
        _on_rule_deleted,
        _on_rule_saved,
        _on_rule_toggled,
        _run_instruction,
        _show_history,
        _show_rules,
        _shutdown,
    )

    for fn in (
        _clear_history,
        _on_feedback,
        _on_rule_deleted,
        _on_rule_saved,
        _on_rule_toggled,
        _run_instruction,
        _shutdown,
        _show_history,
        _show_rules,
    ):
        assert asyncio.iscoroutinefunction(fn), f"{fn.__name__} must be async"
