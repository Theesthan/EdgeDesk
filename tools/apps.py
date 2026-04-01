"""Application launcher tool.

Launches processes via `subprocess.Popen` (explicit args list — no shell=True).
Lists running processes via `psutil.process_iter`.
Includes fuzzy app resolution: tries shutil.which, common name aliases, and
common Windows install directories before giving up.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

import psutil
from langchain_core.tools import BaseTool
from loguru import logger

from schemas.models import AppControlInput, AppLaunchInput, AppLaunchOutput, ToolError

# ---------------------------------------------------------------------------
# App resolution helpers
# ---------------------------------------------------------------------------

# Common aliases: user-friendly name → list of executable names to try
_APP_ALIASES: dict[str, list[str]] = {
    "chrome": ["chrome.exe", "googlechrome.exe"],
    "google chrome": ["chrome.exe", "googlechrome.exe"],
    "firefox": ["firefox.exe"],
    "edge": ["msedge.exe", "MicrosoftEdge.exe"],
    "microsoft edge": ["msedge.exe"],
    "notepad": ["notepad.exe"],
    "notepad++": ["notepad++.exe"],
    "word": ["WINWORD.EXE", "winword.exe"],
    "excel": ["EXCEL.EXE", "excel.exe"],
    "powerpoint": ["POWERPNT.EXE", "powerpnt.exe"],
    "outlook": ["OUTLOOK.EXE", "outlook.exe"],
    "vscode": ["code.exe", "code"],
    "vs code": ["code.exe", "code"],
    "visual studio code": ["code.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "terminal": ["wt.exe", "cmd.exe"],
    "windows terminal": ["wt.exe"],
    "spotify": ["Spotify.exe"],
    "discord": ["Discord.exe"],
    "slack": ["slack.exe"],
    "vlc": ["vlc.exe"],
    "zoom": ["Zoom.exe"],
    "teams": ["Teams.exe"],
    "microsoft teams": ["Teams.exe"],
    "paint 3d": ["PaintStudio.View.exe"],
}

# Directories searched recursively (depth 2) when shutil.which fails
_SEARCH_DIRS: list[Path] = [
    Path("C:/Windows/System32"),
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path.home() / "AppData" / "Local",
    Path.home() / "AppData" / "Roaming",
]


def _resolve_command(raw: list[str]) -> list[str]:
    """Return the best executable path for *raw[0]*, keeping extra args intact.

    Resolution order:
    1. shutil.which — respects PATH as-is
    2. Known alias map → try each candidate via shutil.which
    3. Glob common install directories for an executable matching the name
    Falls back to the original command if nothing is found (lets the OS error speak).
    """
    exe = raw[0]
    rest = raw[1:]

    # 1. Already resolvable via PATH
    if shutil.which(exe):
        return raw

    # 2. Try known aliases
    key = exe.lower().rstrip(".exe")
    candidates = _APP_ALIASES.get(key, []) or _APP_ALIASES.get(exe.lower(), [])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            logger.debug("app_control alias '{}' → '{}'", exe, resolved)
            return [resolved, *rest]

    # 3. Search install directories
    search_name = exe.lower() if exe.lower().endswith(".exe") else exe.lower() + ".exe"
    for base in _SEARCH_DIRS:
        if not base.exists():
            continue
        # Depth-2 search to avoid scanning entire drive
        for depth in (base.glob("*.exe"), base.glob("*/*.exe"), base.glob("*/*/*.exe")):
            for found in depth:
                if found.name.lower() == search_name:
                    logger.debug("app_control found '{}' at '{}'", exe, found)
                    return [str(found), *rest]

    logger.warning("app_control could not resolve '{}', trying as-is", exe)
    return raw


class AppTool(BaseTool):
    """Launch an application or list running processes."""

    name: str = "app_control"
    description: str = "Launch app: action='launch', command=['spotify']. List procs: action='list'."
    args_schema: type = AppControlInput

    def _launch(self, inp: AppLaunchInput) -> AppLaunchOutput | ToolError:
        command = _resolve_command(inp.command)
        try:
            proc = subprocess.Popen(
                command,
                cwd=inp.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("app_control launched pid={} cmd={}", proc.pid, command)
            return AppLaunchOutput(pid=proc.pid, name=command[0])
        except FileNotFoundError:
            msg = (
                f"Could not find '{inp.command[0]}'. "
                f"Make sure it is installed and try a full path or exact executable name."
            )
            logger.error("app_control: {}", msg)
            return ToolError(tool="app_control", message=msg, retryable=False)
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
                return ToolError(
                    tool="app_control", message=f"Invalid input: {exc}", retryable=False
                )
            return self._launch(inp)
        elif action == "list":
            return self._list_processes()
        else:
            return ToolError(
                tool="app_control", message=f"Unknown action: {action!r}", retryable=False
            )

    async def _arun(self, **kwargs: Any) -> Any:  # type: ignore[override]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
