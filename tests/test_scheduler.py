"""Tests for scheduler/triggers.py and scheduler/engine.py."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.crud import create_rule, get_rule, list_executions
from scheduler.engine import SchedulerEngine
from scheduler.triggers import make_trigger

# ===========================================================================
# Helpers / fixtures
# ===========================================================================


class MockOrchestrator:
    """Minimal orchestrator stub that streams a fixed set of tokens."""

    def __init__(self, tokens: list[str] | None = None) -> None:
        self.tokens = tokens or ["done"]
        self.calls: list[str] = []

    async def run(self, instruction: str) -> AsyncIterator[str]:
        self.calls.append(instruction)
        for token in self.tokens:
            yield token


class FailingOrchestrator:
    """Orchestrator that raises on run()."""

    async def run(self, instruction: str) -> AsyncIterator[str]:
        raise RuntimeError("orchestrator boom")
        yield  # make it an async generator


def _make_rule_stub(
    rule_id: str = "r1",
    name: str = "Test Rule",
    trigger_type: str = "manual",
    trigger_config: dict[str, Any] | None = None,
    instruction: str = "do something",
    enabled: bool = True,
) -> MagicMock:
    """Return a mock Rule object with the given attributes."""
    rule = MagicMock()
    rule.id = rule_id
    rule.name = name
    rule.trigger_type = trigger_type
    rule.trigger_config = trigger_config or {}
    rule.instruction = instruction
    rule.enabled = enabled
    return rule


# ===========================================================================
# scheduler/triggers.py
# ===========================================================================


class TestMakeTrigger:
    def test_time_cron_returns_cron_trigger(self) -> None:
        rule = _make_rule_stub(trigger_type="time_cron", trigger_config={"minute": "*/5"})
        trigger = make_trigger(rule)
        assert isinstance(trigger, CronTrigger)

    def test_file_event_returns_interval_trigger(self) -> None:
        rule = _make_rule_stub(trigger_type="file_event")
        trigger = make_trigger(rule)
        assert isinstance(trigger, IntervalTrigger)

    def test_file_event_custom_interval(self) -> None:
        rule = _make_rule_stub(trigger_type="file_event", trigger_config={"interval_seconds": 60})
        trigger = make_trigger(rule)
        assert isinstance(trigger, IntervalTrigger)

    def test_manual_returns_date_trigger(self) -> None:
        rule = _make_rule_stub(trigger_type="manual")
        trigger = make_trigger(rule)
        assert isinstance(trigger, DateTrigger)

    def test_none_trigger_type_defaults_to_manual(self) -> None:
        rule = _make_rule_stub(trigger_type=None)
        trigger = make_trigger(rule)
        assert isinstance(trigger, DateTrigger)

    def test_unknown_trigger_type_raises(self) -> None:
        rule = _make_rule_stub(trigger_type="webhook")
        with pytest.raises(ValueError, match="Unknown trigger_type"):
            make_trigger(rule)

    def test_invalid_cron_config_raises(self) -> None:
        rule = _make_rule_stub(
            trigger_type="time_cron", trigger_config={"not_a_valid_kwarg": "boom"}
        )
        with pytest.raises(ValueError, match="Invalid cron config"):
            make_trigger(rule)

    def test_cron_next_fire_time_is_correct(self) -> None:
        """CronTrigger computes the correct next-fire time for a given 'now'.

        Equivalent to freeze_time: we pass an explicit 'now' to
        get_next_fire_time() instead of using the real clock.
        """
        rule = _make_rule_stub(
            trigger_type="time_cron",
            trigger_config={"hour": "9", "minute": "0"},  # fires at 09:00 UTC daily
        )
        trigger = make_trigger(rule)
        assert isinstance(trigger, CronTrigger)

        # Simulate "now" as 08:30 UTC on 2026-01-15
        frozen_now = datetime(2026, 1, 15, 8, 30, 0, tzinfo=UTC)
        next_fire = trigger.get_next_fire_time(None, frozen_now)

        assert next_fire is not None
        assert next_fire.hour == 9
        assert next_fire.minute == 0
        # Should be same day since 09:00 > 08:30
        assert next_fire.date() == frozen_now.date()

    def test_cron_next_fire_rolls_to_next_day(self) -> None:
        """After 09:00, the next fire is the following day."""
        rule = _make_rule_stub(
            trigger_type="time_cron",
            trigger_config={"hour": "9", "minute": "0"},
        )
        trigger = make_trigger(rule)
        frozen_now = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)  # past 09:00
        next_fire = trigger.get_next_fire_time(None, frozen_now)

        assert next_fire is not None
        assert next_fire.date() == frozen_now.date() + timedelta(days=1)


# ===========================================================================
# scheduler/engine.py — job registration
# ===========================================================================


class TestSchedulerEngineRegistration:
    async def test_start_registers_enabled_rules(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            r1 = await create_rule(
                session,
                name="r1",
                trigger_type="manual",
                enabled=True,
            )
            r2 = await create_rule(
                session,
                name="r2",
                trigger_type="manual",
                enabled=False,  # should NOT be registered
            )
            await session.commit()

        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)

        with patch.object(engine._scheduler, "start"):
            await engine.start()

        assert r1.id in engine.job_ids()
        assert r2.id not in engine.job_ids()

    async def test_start_with_no_rules_is_fine(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)
        with patch.object(engine._scheduler, "start"):
            await engine.start()
        assert engine.job_ids() == []

    async def test_stop_shuts_down_scheduler(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)

        # Patch both start (so APScheduler doesn't need a real event loop)
        # and running (so stop() proceeds to call shutdown)
        with (
            patch.object(engine._scheduler, "start"),
            patch.object(
                type(engine._scheduler),
                "running",
                new_callable=lambda: property(lambda _self: True),
            ),
            patch.object(engine._scheduler, "shutdown") as mock_shutdown,
        ):
            await engine.start()
            await engine.stop()

        mock_shutdown.assert_called_once_with(wait=False)

    async def test_stop_when_not_started_is_safe(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)
        await engine.stop()  # should not raise

    async def test_register_job_with_bad_trigger_is_skipped(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(
                session,
                name="bad-trigger",
                trigger_type="time_cron",
                trigger_config={"invalid_kwarg": "x"},  # will fail
                enabled=True,
            )
            await session.commit()

        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)
        with patch.object(engine._scheduler, "start"):
            await engine.start()  # should not raise
        assert rule.id not in engine.job_ids()


# ===========================================================================
# scheduler/engine.py — reload_rule
# ===========================================================================


class TestSchedulerEngineReloadRule:
    async def _started_engine(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> SchedulerEngine:
        engine = SchedulerEngine(db_session_factory, MockOrchestrator())
        with patch.object(engine._scheduler, "start"):
            await engine.start()
        return engine

    async def test_reload_adds_job_for_enabled_rule(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        # Start the engine BEFORE the rule exists in the DB
        engine = await self._started_engine(db_session_factory)
        assert engine.job_ids() == []

        # Now create the rule
        async with db_session_factory() as session:
            rule = await create_rule(session, name="new-rule", trigger_type="manual", enabled=True)
            await session.commit()
            rule_id = rule.id

        # Job not yet registered — reload_rule should add it
        assert rule_id not in engine.job_ids()
        await engine.reload_rule(rule_id)
        assert rule_id in engine.job_ids()

    async def test_reload_removes_job_for_disabled_rule(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(
                session, name="toggle-rule", trigger_type="manual", enabled=True
            )
            await session.commit()
            rule_id = rule.id

        engine = await self._started_engine(db_session_factory)
        await engine.reload_rule(rule_id)
        assert rule_id in engine.job_ids()

        # Disable the rule then reload
        async with db_session_factory() as session:
            db_rule = await get_rule(session, rule_id)
            assert db_rule is not None
            db_rule.enabled = False
            await session.commit()

        await engine.reload_rule(rule_id)
        assert rule_id not in engine.job_ids()

    async def test_reload_removes_job_for_deleted_rule(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(session, name="del-rule", trigger_type="manual", enabled=True)
            await session.commit()
            rule_id = rule.id

        engine = await self._started_engine(db_session_factory)
        await engine.reload_rule(rule_id)
        assert rule_id in engine.job_ids()

        # Delete the rule from DB
        from db.crud import delete_rule

        async with db_session_factory() as session:
            await delete_rule(session, rule_id)
            await session.commit()

        await engine.reload_rule(rule_id)
        assert rule_id not in engine.job_ids()

    async def test_reload_replaces_existing_job(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """reload_rule on an already-registered rule replaces (not duplicates) it."""
        async with db_session_factory() as session:
            rule = await create_rule(
                session, name="replace-rule", trigger_type="manual", enabled=True
            )
            await session.commit()
            rule_id = rule.id

        engine = await self._started_engine(db_session_factory)
        await engine.reload_rule(rule_id)
        await engine.reload_rule(rule_id)  # second reload

        assert engine.job_ids().count(rule_id) == 1  # not duplicated


# ===========================================================================
# scheduler/engine.py — _fire_rule (execution logging)
# ===========================================================================


class TestSchedulerEngineFire:
    async def test_fire_rule_creates_execution_success(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(
                session,
                name="fire-success",
                trigger_type="manual",
                instruction="say hello",
                enabled=True,
            )
            await session.commit()
            rule_id = rule.id

        orchestrator = MockOrchestrator(tokens=["hello"])
        engine = SchedulerEngine(db_session_factory, orchestrator)
        await engine._fire_rule(rule_id)

        async with db_session_factory() as session:
            execs = await list_executions(session, rule_id=rule_id)

        assert len(execs) == 1
        assert execs[0].status == "success"
        assert execs[0].rule_id == rule_id
        assert execs[0].duration_ms is not None and execs[0].duration_ms >= 0

    async def test_fire_rule_logs_failed_on_orchestrator_error(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(
                session,
                name="fire-fail",
                trigger_type="manual",
                instruction="crash",
                enabled=True,
            )
            await session.commit()
            rule_id = rule.id

        engine = SchedulerEngine(db_session_factory, FailingOrchestrator())
        await engine._fire_rule(rule_id)

        async with db_session_factory() as session:
            execs = await list_executions(session, rule_id=rule_id)

        assert len(execs) == 1
        assert execs[0].status == "failed"

    async def test_fire_rule_skips_missing_rule(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)
        await engine._fire_rule("nonexistent-rule-id")  # must not raise

        # No execution records should be created
        async with db_session_factory() as session:
            execs = await list_executions(session)
        assert len(execs) == 0

    async def test_fire_rule_orchestrator_called_with_instruction(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(
                session,
                name="instruction-test",
                trigger_type="manual",
                instruction="open notepad",
                enabled=True,
            )
            await session.commit()
            rule_id = rule.id

        orchestrator = MockOrchestrator()
        engine = SchedulerEngine(db_session_factory, orchestrator)
        await engine._fire_rule(rule_id)

        assert orchestrator.calls == ["open notepad"]

    async def test_fire_rule_creates_execution_with_duration(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            rule = await create_rule(
                session,
                name="timed-rule",
                trigger_type="manual",
                instruction="timed task",
                enabled=True,
            )
            await session.commit()
            rule_id = rule.id

        orchestrator = MockOrchestrator(tokens=["a", "b", "c"])
        engine = SchedulerEngine(db_session_factory, orchestrator)
        await engine._fire_rule(rule_id)

        async with db_session_factory() as session:
            execs = await list_executions(session, rule_id=rule_id)

        assert execs[0].duration_ms >= 0


# ===========================================================================
# engine properties
# ===========================================================================


class TestSchedulerEngineProperties:
    async def test_running_false_before_start(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        engine = SchedulerEngine(db_session_factory, MockOrchestrator())
        assert engine.running is False

    async def test_job_ids_empty_before_start(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        engine = SchedulerEngine(db_session_factory, MockOrchestrator())
        assert engine.job_ids() == []
