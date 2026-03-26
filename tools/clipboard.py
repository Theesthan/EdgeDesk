"""Clipboard tool.

Reads from and writes to the system clipboard via `pyperclip`.
"""

from __future__ import annotations

from typing import Any

import pyperclip
from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import ClipboardReadOutput, ClipboardWriteInput, ToolError


class ClipboardTool(BaseTool):
    """Read from or write text to the system clipboard."""

    name: str = "clipboard"
    description: str = "Read current clipboard text or write new text to clipboard."
    args_schema: type = ClipboardWriteInput

    def _read(self) -> ClipboardReadOutput | ToolError:
        try:
            text: str = pyperclip.paste()
            return ClipboardReadOutput(text=text)
        except Exception as exc:
            logger.error("clipboard read failed: {}", exc)
            return ToolError(tool="clipboard", message=str(exc), retryable=True)

    def _write(self, inp: ClipboardWriteInput) -> dict[str, Any] | ToolError:
        try:
            pyperclip.copy(inp.text)
            return {"copied": True, "length": len(inp.text)}
        except Exception as exc:
            logger.error("clipboard write failed: {}", exc)
            return ToolError(tool="clipboard", message=str(exc), retryable=True)

    def _run(self, action: str = "read", **kwargs: Any) -> Any:  # type: ignore[override]
        logger.debug("clipboard action={}", action)
        if action == "read":
            return self._read()
        elif action == "write":
            try:
                inp = ClipboardWriteInput(**kwargs)
            except Exception as exc:
                return ToolError(tool="clipboard", message=f"Invalid input: {exc}", retryable=False)
            return self._write(inp)
        else:
            return ToolError(
                tool="clipboard", message=f"Unknown action: {action!r}", retryable=False
            )

    async def _arun(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._run(**kwargs)
