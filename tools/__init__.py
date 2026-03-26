"""EdgeDesk tool manifest.

Imports and exposes all LangChain BaseTool instances as `TOOL_MANIFEST`.
The AgentOrchestrator receives this list — never imports tools directly.
"""

from __future__ import annotations

from tools.apps import AppTool
from tools.clipboard import ClipboardTool
from tools.email_reader import EmailTool
from tools.files import FileTool
from tools.gui import GUITool
from tools.notify import NotifyTool
from tools.screen import ScreenTool

TOOL_MANIFEST: list = [
    ScreenTool(),
    GUITool(),
    FileTool(),
    AppTool(),
    ClipboardTool(),
    NotifyTool(),
    EmailTool(),
]

__all__ = ["TOOL_MANIFEST"]
