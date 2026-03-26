"""Desktop notification tool.

Sends a native desktop notification via `plyer`.
On platforms where plyer has no backend, falls back to a log message.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import NotifyInput, ToolError

try:
    from plyer import notification
except Exception:
    notification = None  # type: ignore[assignment]


class NotifyTool(BaseTool):
    """Show a native desktop notification with title, message, and timeout."""

    name: str = "notify"
    description: str = "Show a native desktop notification with a title and message."
    args_schema: type = NotifyInput

    def _run(self, **kwargs: Any) -> dict[str, Any] | ToolError:
        try:
            inp = NotifyInput(**kwargs)
        except Exception as exc:
            return ToolError(tool="notify", message=f"Invalid input: {exc}", retryable=False)

        logger.debug("notify title={!r} timeout={}s", inp.title, inp.timeout)
        try:
            if notification is None:
                raise RuntimeError("plyer is not available on this platform.")
            notification.notify(
                title=inp.title,
                message=inp.message,
                timeout=inp.timeout,
            )
            return {"sent": True, "title": inp.title}
        except Exception as exc:
            logger.error("notify failed: {}", exc)
            return ToolError(tool="notify", message=str(exc), retryable=False)

    async def _arun(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._run(**kwargs)
