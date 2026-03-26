"""Application launcher tool.

Launches processes via `subprocess.Popen` (explicit args list — no shell=True).
Lists running processes via `psutil.process_iter`.
"""

from __future__ import annotations

import subprocess
from typing import Any

import psutil
from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import AppLaunchInput, AppLaunchOutput, ToolError


class AppTool(BaseTool):
    """Launch an application or list running processes."""

    name: str = "app_control"
    description: str = "Launch an application by command or list running processes."
    args_schema: type = AppLaunchInput

    def _launch(self, inp: AppLaunchInput) -> AppLaunchOutput | ToolError:
        try:
            proc = subprocess.Popen(
                inp.command,
                cwd=inp.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("app_control launched pid={} cmd={}", proc.pid, inp.command)
            return AppLaunchOutput(pid=proc.pid, name=inp.command[0])
        except Exception as exc:
            logger.error("app_control launch failed: {}", exc)
            return ToolError(tool="app_control", message=str(exc), retryable=False)

    def _list_processes(self) -> dict[str, Any]:
        procs = [
            {"pid": p.pid, "name": p.name(), "status": p.status()}
            for p in psutil.process_iter(["pid", "name", "status"])
            if p.info["name"]
        ]
        return {"processes": procs, "count": len(procs)}

    def _run(self, action: str = "launch", **kwargs: Any) -> Any:  # type: ignore[override]
        logger.debug("app_control action={}", action)
        if action == "launch":
            try:
                inp = AppLaunchInput(**kwargs)
            except Exception as exc:
                return ToolError(tool="app_control", message=f"Invalid input: {exc}", retryable=False)
            return self._launch(inp)
        elif action == "list":
            return self._list_processes()
        else:
            return ToolError(tool="app_control", message=f"Unknown action: {action!r}", retryable=False)

    async def _arun(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._run(**kwargs)
