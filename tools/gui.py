"""GUI automation tool via PyAutoGUI.

Provides click, type, scroll, hotkey, and wait actions with automatic retry
logic (max 3 attempts, exponential backoff: 0.5s, 1.0s, 2.0s).

Key implementation notes:
- `type` uses clipboard paste (pyperclip + ctrl+v) instead of typewrite so it
  works reliably in Electron apps (Spotify, Discord, VS Code, etc.)
- `wait` pauses execution for N seconds — use it after launching apps to let
  them fully load before taking further action
- pyautogui.PAUSE is set to 50 ms at module load for reliability
- FailSafeException (mouse at corner) is caught and returned as ToolError
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pyautogui
import pyperclip
from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import (
    GUIActionInput,
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
    """Click, type, scroll, press hotkeys, or wait on the desktop GUI."""

    name: str = "gui_action"
    description: str = "Click, type (via paste), scroll, press hotkeys, or wait for apps to load."
    args_schema: type = GUIActionInput

    # ------------------------------------------------------------------ #
    # Internal dispatch
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
        """Type text using clipboard paste for reliability in all apps.

        Saves and restores the existing clipboard content so we don't clobber
        the user's clipboard unexpectedly.
        """
        try:
            # Save existing clipboard
            try:
                original = pyperclip.paste()
            except Exception:
                original = ""

            pyperclip.copy(inp.text)
            time.sleep(0.05)  # let clipboard settle
            _with_retry(pyautogui.hotkey, "ctrl", "v")
            time.sleep(0.05)

            # Restore original clipboard
            try:
                pyperclip.copy(original)
            except Exception:
                pass

            return GUIActionOutput(success=True, message=f"Typed {len(inp.text)} chars via paste")
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

    def _wait(self, seconds: float) -> GUIActionOutput:
        clamped = max(0.1, min(seconds, 30.0))
        time.sleep(clamped)
        return GUIActionOutput(success=True, message=f"Waited {clamped:.1f}s")

    # ------------------------------------------------------------------ #
    # LangChain interface
    # ------------------------------------------------------------------ #

    def _run(self, action: str, **kwargs: Any) -> GUIActionOutput | ToolError:  # type: ignore[override]
        """Dispatch to the correct GUI action based on *action* string."""
        logger.debug("gui_action action={} kwargs={}", action, kwargs)
        if action == "click":
            try:
                inp = GUIClickInput(**kwargs)
            except Exception as exc:
                return ToolError(tool="gui_click", message=f"Invalid input: {exc}", retryable=False)
            return self._click(inp)
        elif action == "type":
            try:
                inp = GUITypeInput(**kwargs)
            except Exception as exc:
                return ToolError(tool="gui_type", message=f"Invalid input: {exc}", retryable=False)
            return self._type(inp)
        elif action == "scroll":
            try:
                inp = GUIScrollInput(**kwargs)
            except Exception as exc:
                return ToolError(
                    tool="gui_scroll", message=f"Invalid input: {exc}", retryable=False
                )
            return self._scroll(inp)
        elif action == "hotkey":
            try:
                inp = GUIHotkeyInput(**kwargs)
            except Exception as exc:
                return ToolError(
                    tool="gui_hotkey", message=f"Invalid input: {exc}", retryable=False
                )
            return self._hotkey(inp)
        elif action == "wait":
            seconds = float(kwargs.get("seconds", 2.0))
            return self._wait(seconds)
        else:
            return ToolError(
                tool="gui_action", message=f"Unknown action: {action!r}", retryable=False
            )

    async def _arun(self, action: str, **kwargs: Any) -> GUIActionOutput | ToolError:  # type: ignore[override]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(action, **kwargs))
