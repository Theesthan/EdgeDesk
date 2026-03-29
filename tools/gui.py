"""GUI automation tool via PyAutoGUI.

Provides click, type, scroll, and hotkey actions with automatic retry
logic (max 3 attempts, exponential backoff: 0.5s, 1.0s, 2.0s).

pyautogui.PAUSE is set to 50 ms at module load for reliability.
FailSafeException (mouse at corner) is caught and returned as ToolError.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pyautogui
from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import (
    GUIActionOutput,
    GUIClickInput,
    GUIHotkeyInput,
    GUIScrollInput,
    GUITypeInput,
    ToolError,
)

# Global safety pause between consecutive PyAutoGUI calls
pyautogui.PAUSE = 0.05

_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 0.5  # seconds


def _with_retry(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call *fn* with *args/kwargs*, retrying on transient errors.

    Raises the final exception if all retries are exhausted.
    FailSafeException is re-raised immediately (not retried).
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except pyautogui.FailSafeException:
            raise
        except Exception as exc:
            last_exc = exc
            wait = _BACKOFF_BASE * (2**attempt)
            logger.warning(
                "GUI action failed (attempt {}/{}): {} — retrying in {}s",
                attempt + 1,
                _MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


class GUITool(BaseTool):
    """Click, type, scroll, or press hotkeys on the desktop GUI."""

    name: str = "gui_action"
    description: str = "Perform GUI actions: click, type text, scroll, or press hotkeys."
    args_schema: type = GUIClickInput  # overridden per action via run()

    # ------------------------------------------------------------------ #
    # Internal dispatch — called by _run after input parsing
    # ------------------------------------------------------------------ #

    def _click(self, inp: GUIClickInput) -> GUIActionOutput | ToolError:
        try:
            _with_retry(pyautogui.click, inp.x, inp.y, clicks=inp.clicks, button=inp.button)
            return GUIActionOutput(success=True, message=f"Clicked ({inp.x}, {inp.y})")
        except pyautogui.FailSafeException:
            return ToolError(
                tool="gui_click", message="FailSafe: mouse moved to corner.", retryable=False
            )
        except Exception as exc:
            return ToolError(tool="gui_click", message=str(exc), retryable=True)

    def _type(self, inp: GUITypeInput) -> GUIActionOutput | ToolError:
        try:
            _with_retry(pyautogui.typewrite, inp.text, interval=inp.interval)
            return GUIActionOutput(success=True, message=f"Typed {len(inp.text)} chars")
        except pyautogui.FailSafeException:
            return ToolError(
                tool="gui_type", message="FailSafe: mouse moved to corner.", retryable=False
            )
        except Exception as exc:
            return ToolError(tool="gui_type", message=str(exc), retryable=True)

    def _scroll(self, inp: GUIScrollInput) -> GUIActionOutput | ToolError:
        try:
            _with_retry(pyautogui.scroll, inp.clicks, x=inp.x, y=inp.y)
            return GUIActionOutput(
                success=True, message=f"Scrolled {inp.clicks} at ({inp.x}, {inp.y})"
            )
        except pyautogui.FailSafeException:
            return ToolError(
                tool="gui_scroll", message="FailSafe: mouse moved to corner.", retryable=False
            )
        except Exception as exc:
            return ToolError(tool="gui_scroll", message=str(exc), retryable=True)

    def _hotkey(self, inp: GUIHotkeyInput) -> GUIActionOutput | ToolError:
        try:
            _with_retry(pyautogui.hotkey, *inp.keys)
            return GUIActionOutput(success=True, message=f"Hotkey: {'+'.join(inp.keys)}")
        except pyautogui.FailSafeException:
            return ToolError(
                tool="gui_hotkey", message="FailSafe: mouse moved to corner.", retryable=False
            )
        except Exception as exc:
            return ToolError(tool="gui_hotkey", message=str(exc), retryable=True)

    # ------------------------------------------------------------------ #
    # LangChain interface — action dispatched by "action" field
    # ------------------------------------------------------------------ #

    def _run(self, action: str, **kwargs: Any) -> GUIActionOutput | ToolError:  # type: ignore[override]
        """Dispatch to the correct GUI action based on *action* string."""
        logger.debug("gui_action action={} kwargs={}", action, kwargs)
        if action == "click":
            try:
                click_inp = GUIClickInput(**kwargs)
            except Exception as exc:
                return ToolError(tool="gui_click", message=f"Invalid input: {exc}", retryable=False)
            return self._click(click_inp)
        elif action == "type":
            try:
                type_inp = GUITypeInput(**kwargs)
            except Exception as exc:
                return ToolError(tool="gui_type", message=f"Invalid input: {exc}", retryable=False)
            return self._type(type_inp)
        elif action == "scroll":
            try:
                scroll_inp = GUIScrollInput(**kwargs)
            except Exception as exc:
                return ToolError(
                    tool="gui_scroll", message=f"Invalid input: {exc}", retryable=False
                )
            return self._scroll(scroll_inp)
        elif action == "hotkey":
            try:
                hotkey_inp = GUIHotkeyInput(**kwargs)
            except Exception as exc:
                return ToolError(
                    tool="gui_hotkey", message=f"Invalid input: {exc}", retryable=False
                )
            return self._hotkey(hotkey_inp)
        else:
            return ToolError(
                tool="gui_action", message=f"Unknown action: {action!r}", retryable=False
            )

    async def _arun(self, action: str, **kwargs: Any) -> GUIActionOutput | ToolError:  # type: ignore[override]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(action, **kwargs))
