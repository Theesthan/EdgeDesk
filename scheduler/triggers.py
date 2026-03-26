"""APScheduler trigger factory for EdgeDesk rules.

Maps each Rule.trigger_type to the appropriate APScheduler trigger:

  time_cron   → CronTrigger(**trigger_config)
  file_event  → IntervalTrigger(seconds=30) — polls for file changes
  manual      → DateTrigger(run_date=now)   — fires once immediately
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

if TYPE_CHECKING:
    from apscheduler.triggers.base import BaseTrigger

    from db.models import Rule

_DEFAULT_FILE_POLL_SECONDS: int = 30


def make_trigger(rule: Rule) -> BaseTrigger:
    """Return an APScheduler trigger for *rule*.

    Args:
        rule: A `Rule` ORM instance with `trigger_type` and `trigger_config`.

    Returns:
        An APScheduler `BaseTrigger` subclass.

    Raises:
        ValueError: If `trigger_type` is unrecognised or `trigger_config` is
            invalid for the requested trigger type.
    """
    trigger_type: str = rule.trigger_type or "manual"
    config: dict[str, Any] = rule.trigger_config or {}

    if trigger_type == "time_cron":
        try:
            trigger = CronTrigger(timezone="UTC", **config)
            logger.debug("CronTrigger created for rule {!r}: {}", rule.id, config)
            return trigger
        except Exception as exc:
            raise ValueError(
                f"Invalid cron config for rule {rule.id!r}: {exc}"
            ) from exc

    elif trigger_type == "file_event":
        interval = int(config.get("interval_seconds", _DEFAULT_FILE_POLL_SECONDS))
        logger.debug("IntervalTrigger {}s for file_event rule {!r}", interval, rule.id)
        return IntervalTrigger(seconds=interval)

    elif trigger_type == "manual":
        run_date = datetime.now(UTC)
        logger.debug("DateTrigger (immediate) for manual rule {!r}", rule.id)
        return DateTrigger(run_date=run_date)

    else:
        raise ValueError(
            f"Unknown trigger_type {trigger_type!r} for rule {rule.id!r}. "
            "Expected one of: 'time_cron', 'file_event', 'manual'."
        )
