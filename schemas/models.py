"""Pydantic v2 I/O schemas for all EdgeDesk agent tools.

Every tool's input AND output has a typed model here.
The agent never receives or returns raw dicts — always use these schemas.

Validators on action fields coerce single-element lists to strings so small
LLMs that wrap scalar values in lists (e.g. action=['launch']) still work.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class ToolError(BaseModel):
    """Returned by any tool on failure — never raises to the agent."""

    tool: str = Field(description="Name of the tool that failed.")
    message: str = Field(description="Human-readable error description.")
    retryable: bool = Field(default=False, description="Whether the agent should retry.")


# ---------------------------------------------------------------------------
# Screen / OCR
# ---------------------------------------------------------------------------


class ScreenCaptureInput(BaseModel):
    """Capture a region of the screen and run OCR."""

    region: tuple[int, int, int, int] | None = Field(
        default=None,
        description="Optional (left, top, width, height). Full screen if None.",
    )

    @field_validator("region")
    @classmethod
    def region_positive(
        cls, v: tuple[int, int, int, int] | None
    ) -> tuple[int, int, int, int] | None:
        if v is not None and (v[2] <= 0 or v[3] <= 0):
            raise ValueError("Region width and height must be positive.")
        return v


class ScreenCaptureOutput(BaseModel):
    """OCR result from a screen capture."""

    text: str = Field(description="Extracted text from the screen region.")
    image_path: str | None = Field(
        default=None, description="Path to the saved screenshot, if requested."
    )


# ---------------------------------------------------------------------------
# GUI Interaction
# ---------------------------------------------------------------------------


class GUIClickInput(BaseModel):
    """Click a screen coordinate."""

    x: int = Field(ge=0, description="X screen coordinate in pixels.")
    y: int = Field(ge=0, description="Y screen coordinate in pixels.")
    button: Literal["left", "right", "middle"] = Field(default="left")
    clicks: int = Field(default=1, ge=1, le=3)


class GUITypeInput(BaseModel):
    """Type text at the current cursor position."""

    text: str = Field(min_length=1, description="Text to type.")
    interval: float = Field(default=0.05, ge=0.0, description="Seconds between keystrokes.")


class GUIScrollInput(BaseModel):
    """Scroll at a screen coordinate."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    clicks: int = Field(description="Positive = scroll up, negative = scroll down.")


class GUIHotkeyInput(BaseModel):
    """Press a keyboard shortcut (e.g. ctrl+c)."""

    keys: list[str] = Field(min_length=1, description="Keys to press simultaneously.")


class GUIActionInput(BaseModel):
    """Unified schema for all GUI actions passed to the gui_action tool."""

    action: Literal["click", "type", "scroll", "hotkey", "wait"] = Field(
        description=(
            "Action to perform. Must be exactly one of: click, type, scroll, hotkey, wait. "
            "Use wait after launching apps."
        )
    )
    # click / scroll fields
    x: int = Field(default=0, ge=0, description="X pixel coordinate (click/scroll).")
    y: int = Field(default=0, ge=0, description="Y pixel coordinate (click/scroll).")
    button: Literal["left", "right", "middle"] = Field(
        default="left", description="Mouse button (click only)."
    )
    clicks: int = Field(default=1, ge=1, le=3, description="Number of clicks.")
    # type fields
    text: str = Field(default="", description="Text to type (type action).")
    interval: float = Field(default=0.05, ge=0.0, description="Seconds between keystrokes.")
    # hotkey fields
    keys: list[str] = Field(
        default_factory=list, description="Keys to press simultaneously (hotkey action)."
    )
    # wait fields
    seconds: float = Field(
        default=2.0, ge=0.1, le=30.0, description="Seconds to wait (wait action)."
    )

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v: Any) -> Any:
        """Accept ['click'] in addition to 'click' — guards against LLM list-wrapping."""
        if isinstance(v, list) and len(v) >= 1:
            return v[0]
        return v

    @field_validator("keys", mode="before")
    @classmethod
    def coerce_keys(cls, v: Any) -> Any:
        """Accept 'ctrl' in addition to ['ctrl']."""
        if isinstance(v, str):
            return [v]
        return v


class GUIActionOutput(BaseModel):
    """Result of any GUI action."""

    success: bool
    message: str = Field(default="")


# ---------------------------------------------------------------------------
# File Operations
# ---------------------------------------------------------------------------


class FileReadInput(BaseModel):
    """Read a text file from disk."""

    path: str = Field(description="Absolute or home-relative path to the file.")

    @field_validator("path")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal ('..') is not allowed.")
        return v


class FileReadOutput(BaseModel):
    """Contents of a text file."""

    content: str
    encoding: str = Field(default="utf-8")
    size_bytes: int


class FileWriteInput(BaseModel):
    """Write content to a file, creating it if needed."""

    path: str = Field(description="Destination file path.")
    content: str
    encoding: str = Field(default="utf-8")
    overwrite: bool = Field(default=True)

    @field_validator("path")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal ('..') is not allowed.")
        return v


class FileMoveInput(BaseModel):
    """Move or rename a file."""

    src: str = Field(description="Source path.")
    dst: str = Field(description="Destination path.")

    @field_validator("src", "dst")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal ('..') is not allowed.")
        return v


class FileMoveOutput(BaseModel):
    """Result of a file move operation."""

    new_path: str


class FileOpInput(BaseModel):
    """Unified schema for all file operations passed to the file_op tool."""

    action: Literal["read", "write", "move", "delete", "list"] = Field(
        description="Action: read, write, move, delete, or list files."
    )
    path: str = Field(default="", description="File path (read/write/delete/list).")
    content: str = Field(default="", description="Content to write (write action).")
    encoding: str = Field(default="utf-8")
    overwrite: bool = Field(default=True, description="Overwrite existing file (write action).")
    src: str = Field(default="", description="Source path (move action).")
    dst: str = Field(default="", description="Destination path (move action).")

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v: Any) -> Any:
        if isinstance(v, list) and len(v) >= 1:
            return v[0]
        return v


# ---------------------------------------------------------------------------
# App Launcher
# ---------------------------------------------------------------------------


class AppLaunchInput(BaseModel):
    """Launch an application via subprocess."""

    command: list[str] = Field(
        min_length=1, description="Command and args list, e.g. ['notepad', 'file.txt']."
    )
    cwd: str | None = Field(default=None, description="Working directory.")


class AppLaunchOutput(BaseModel):
    """Launched process info."""

    pid: int
    name: str


class AppControlInput(BaseModel):
    """Unified schema for app_control tool.

    Examples
    --------
    Launch Spotify:  action='launch', command=['spotify']
    Launch Notepad:  action='launch', command=['notepad']
    List processes:  action='list'
    """

    action: Literal["launch", "list"] = Field(
        description=(
            "Must be the string 'launch' (to open an app) or 'list' (to show running apps). "
            "Never pass a list — just the plain string."
        )
    )
    command: list[str] = Field(
        default_factory=list,
        description=(
            "App name as a list with one string, e.g. ['spotify'] or ['notepad']. "
            "Required when action='launch'."
        ),
    )
    cwd: str | None = Field(default=None, description="Working directory (launch action).")

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v: Any) -> Any:
        """Accept ['launch'] in addition to 'launch' — guards against LLM list-wrapping."""
        if isinstance(v, list) and len(v) >= 1:
            return str(v[0])
        return v

    @field_validator("command", mode="before")
    @classmethod
    def coerce_command(cls, v: Any) -> Any:
        """Accept 'spotify' in addition to ['spotify']."""
        if isinstance(v, str):
            return [v]
        return v

    @model_validator(mode="after")
    def validate_launch_has_command(self) -> "AppControlInput":
        if self.action == "launch" and not self.command:
            raise ValueError(
                "command must not be empty when action='launch'. "
                "Example: action='launch', command=['spotify']"
            )
        return self


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


class ClipboardWriteInput(BaseModel):
    """Write text to the system clipboard."""

    text: str


class ClipboardReadOutput(BaseModel):
    """Current clipboard text."""

    text: str


class ClipboardInput(BaseModel):
    """Unified schema for clipboard tool."""

    action: Literal["read", "write"] = Field(
        description="Action: read current clipboard text or write new text."
    )
    text: str = Field(default="", description="Text to copy (write action).")

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v: Any) -> Any:
        if isinstance(v, list) and len(v) >= 1:
            return v[0]
        return v


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotifyInput(BaseModel):
    """Show a desktop notification."""

    title: str = Field(max_length=64)
    message: str = Field(max_length=256)
    timeout: int = Field(default=5, ge=1, le=30)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


class EmailItem(BaseModel):
    """A single email message."""

    uid: str
    subject: str
    sender: str
    date: str
    body: str


class EmailListInput(BaseModel):
    """List emails from an IMAP folder."""

    folder: str = Field(default="INBOX")
    limit: int = Field(default=10, ge=1, le=100)


class EmailListOutput(BaseModel):
    """List of fetched email items."""

    emails: list[EmailItem]
    total: int
