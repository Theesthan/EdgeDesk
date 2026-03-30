"""Scheduler engine — APScheduler wired to the EdgeDesk rules database.

`SchedulerEngine` owns one `AsyncIOScheduler` instance. On `start()` it
loads all enabled rules from the DB and registers a job per rule. Jobs call
`_fire_rule()` which runs the `AgentOrchestrator` and logs the result to the
`executions` table.

`reload_rule(rule_id)` lets the UI/CRUD layer push incremental updates
without restarting the entire scheduler.
"""

from __future__ import annotations

import json
import time
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.crud import create_execution, get_rule, list_rules
from db.models import Rule
from scheduler.triggers import make_trigger


class SchedulerEngine:
    """Manages APScheduler jobs backed by the EdgeDesk rules database.

    Args:
        session_factory: An `async_sessionmaker` that produces `AsyncSession`
            instances for DB access inside job callbacks.
        orchestrator: The `AgentOrchestrator` used to execute rule instructions.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        orchestrator: Any,
    ) -> None:
        self._session_factory = session_factory
        self._orchestrator = orchestrator
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Load all enabled rules from DB, register jobs, start the scheduler."""
        async with self._session_factory() as session:
            rules = await list_rules(session, enabled_only=True)

        for rule in rules:
            self._register_job(rule)

        self._scheduler.start()
        logger.info(
            "SchedulerEngine started — {} job(s) registered",
            len(self._scheduler.get_jobs()),
        )

    async def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        logger.info("SchedulerEngine stopped")

    # ------------------------------------------------------------------ #
    # Job management
    # ------------------------------------------------------------------ #

    def _register_job(self, rule: Rule) -> None:
        """Add (or replace) a scheduled job for *rule*."""
        try:
            trigger = make_trigger(rule)
        except ValueError as exc:
            logger.warning("Skipping rule {!r} — bad trigger config: {}", rule.id, exc)
            return

        self._scheduler.add_job(
            self._fire_rule,
            trigger=trigger,
            id=rule.id,
            args=[rule.id],
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("Registered job for rule {!r} ({})", rule.name, rule.trigger_type)

    async def reload_rule(self, rule_id: str) -> None:
        """Re-sync the scheduler job for a single rule.

        Removes the existing job (if any) and re-adds it if the rule is
        still enabled. Call this after any CRUD change to a rule.
        """
        if self._scheduler.get_job(rule_id) is not None:
            self._scheduler.remove_job(rule_id)
            logger.debug("Removed existing job for rule {}", rule_id)

        async with self._session_factory() as session:
            rule = await get_rule(session, rule_id)

        if rule is not None and rule.enabled:
            self._register_job(rule)
        else:
            logger.info(
                "Rule {} is {} — no job registered",
                rule_id,
                "disabled" if rule else "deleted",
            )

    # ------------------------------------------------------------------ #
    # Job callback
    # ------------------------------------------------------------------ #

    async def _fire_rule(self, rule_id: str) -> None:
        """Execute a rule's instruction and persist an execution record.

        This is the APScheduler job callback. It:
        1. Loads the rule from the DB — returns early if rule is missing.
        2. Streams all tokens from `orchestrator.run()`.
        3. Writes an `Execution` record with status + duration.
        """
        logger.info("Firing rule {}", rule_id)
        start_ms: int = int(time.monotonic() * 1000)

        async with self._session_factory() as session:
            rule = await get_rule(session, rule_id)

        if rule is None:
            logger.warning("Rule {} not found at fire time — skipping", rule_id)
            return

        instruction: str = rule.instruction or ""
        status: str = "failed"

        try:
            status = "success"
            async for token in self._orchestrator.run(instruction):
                # AgentOrchestrator yields a ToolError JSON on failure instead of raising
                try:
                    payload = json.loads(token)
                    if (
                        isinstance(payload, dict)
                        and "tool" in payload
                        and "retryable" in payload
                    ):
                        status = "failed"
                        logger.warning(
                            "Rule {} agent error: {}", rule_id, payload.get("message", "")
                        )
                except (json.JSONDecodeError, ValueError):
                    pass  # Normal text token
        except Exception as exc:
            logger.error("Rule {} raised during execution: {}", rule_id, exc)
            status = "failed"

        duration_ms: int = int(time.monotonic() * 1000) - start_ms
        try:
            async with self._session_factory() as session:
                await create_execution(
                    session,
                    instruction=instruction,
                    rule_id=rule_id,
                    status=status,
                    duration_ms=duration_ms,
                )
                await session.commit()
            logger.info(
                "Rule {} completed — status={} duration={}ms",
                rule_id,
                status,
                duration_ms,
            )
        except Exception as exc:
            logger.error("Failed to log execution for rule {}: {}", rule_id, exc)

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    @property
    def running(self) -> bool:
        """True if the underlying APScheduler is currently running."""
        return self._scheduler.running

    def job_ids(self) -> list[str]:
        """Return the list of currently registered job IDs."""
        return [job.id for job in self._scheduler.get_jobs()]
