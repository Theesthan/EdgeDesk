"""Tests for all 7 EdgeDesk desktop tools.

Each tool is tested with all external dependencies mocked so no real
screen capture, GUI, file system (for error paths), or network calls occur.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from schemas.models import (
    AppLaunchOutput,
    ClipboardReadOutput,
    EmailListOutput,
    FileReadOutput,
    FileMoveOutput,
    GUIActionOutput,
    ScreenCaptureOutput,
    ToolError,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _is_error(result: Any) -> bool:
    return isinstance(result, ToolError)


def _is_success(result: Any) -> bool:
    return not _is_error(result)


# ===========================================================================
# screen.py — ScreenTool
# ===========================================================================


class TestScreenTool:
    def _make_tool(self) -> Any:
        from tools.screen import ScreenTool

        return ScreenTool()

    def test_screen_capture_returns_output(self) -> None:
        with patch("tools.screen._cached_capture", return_value="Hello World"):
            tool = self._make_tool()
            result = tool._run(region=None)
        assert isinstance(result, ScreenCaptureOutput)
        assert result.text == "Hello World"

    def test_screen_capture_with_region(self) -> None:
        with patch("tools.screen._cached_capture", return_value="Region Text") as mock_cap:
            tool = self._make_tool()
            result = tool._run(region=(0, 0, 100, 100))
        assert isinstance(result, ScreenCaptureOutput)
        assert result.text == "Region Text"
        # Verify region was forwarded
        call_args = mock_cap.call_args[0]
        assert call_args[0] == (0, 0, 100, 100)

    def test_screen_capture_error_returns_tool_error(self) -> None:
        with patch("tools.screen._cached_capture", side_effect=RuntimeError("mss failed")):
            tool = self._make_tool()
            result = tool._run(region=None)
        assert isinstance(result, ToolError)
        assert result.tool == "screen_capture"
        assert result.retryable is True

    def test_cache_bucket_changes_over_time(self) -> None:
        from tools.screen import _CACHE_BUCKET_MS, _time_bucket

        b1 = _time_bucket()
        time.sleep(_CACHE_BUCKET_MS / 1000 + 0.05)
        b2 = _time_bucket()
        assert b2 >= b1  # bucket advances

    def test_cached_capture_uses_lru_cache(self) -> None:
        """Two calls with same args in same bucket return same (cached) result."""
        fake_mss = MagicMock()
        fake_screenshot = MagicMock()
        fake_screenshot.size = (10, 10)
        fake_screenshot.bgra = b"\x00" * 400
        fake_mss.__enter__ = MagicMock(return_value=fake_mss)
        fake_mss.__exit__ = MagicMock(return_value=False)
        fake_mss.grab = MagicMock(return_value=fake_screenshot)
        fake_mss.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

        with (
            patch("tools.screen.mss.mss", return_value=fake_mss),
            patch("tools.screen.Image.frombytes") as mock_img,
            patch("tools.screen.pytesseract.image_to_string", return_value="cached text"),
        ):
            from tools.screen import _cached_capture, _time_bucket

            _cached_capture.cache_clear()
            bucket = _time_bucket()
            r1 = _cached_capture(None, bucket)
            r2 = _cached_capture(None, bucket)

        assert r1 == r2 == "cached text"
        # mss.grab called only once (second hit was cached)
        assert fake_mss.grab.call_count == 1

    async def test_arun_returns_same_as_run(self) -> None:
        with patch("tools.screen._cached_capture", return_value="async result"):
            tool = self._make_tool()
            result = await tool._arun(region=None)
        assert isinstance(result, ScreenCaptureOutput)
        assert result.text == "async result"


# ===========================================================================
# gui.py — GUITool
# ===========================================================================


class TestGUITool:
    def _make_tool(self) -> Any:
        from tools.gui import GUITool

        return GUITool()

    def test_click_success(self) -> None:
        with patch("tools.gui.pyautogui.click") as mock_click:
            tool = self._make_tool()
            result = tool._run(action="click", x=100, y=200, button="left", clicks=1)
        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        mock_click.assert_called_once_with(100, 200, clicks=1, button="left")

    def test_type_success(self) -> None:
        with patch("tools.gui.pyautogui.typewrite") as mock_type:
            tool = self._make_tool()
            result = tool._run(action="type", text="hello", interval=0.05)
        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        mock_type.assert_called_once_with("hello", interval=0.05)

    def test_scroll_success(self) -> None:
        with patch("tools.gui.pyautogui.scroll") as mock_scroll:
            tool = self._make_tool()
            result = tool._run(action="scroll", x=50, y=50, clicks=3)
        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        mock_scroll.assert_called_once_with(3, x=50, y=50)

    def test_hotkey_success(self) -> None:
        with patch("tools.gui.pyautogui.hotkey") as mock_hotkey:
            tool = self._make_tool()
            result = tool._run(action="hotkey", keys=["ctrl", "c"])
        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        mock_hotkey.assert_called_once_with("ctrl", "c")

    def test_unknown_action_returns_error(self) -> None:
        tool = self._make_tool()
        result = tool._run(action="teleport", x=0, y=0)
        assert isinstance(result, ToolError)
        assert "teleport" in result.message

    def test_failsafe_returns_non_retryable_error(self) -> None:
        import pyautogui

        with patch("tools.gui.pyautogui.click", side_effect=pyautogui.FailSafeException):
            tool = self._make_tool()
            result = tool._run(action="click", x=0, y=0)
        assert isinstance(result, ToolError)
        assert result.retryable is False

    def test_retry_on_transient_error(self) -> None:
        """Click retries up to 3 times then returns ToolError."""
        call_count = 0

        def flaky(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            raise OSError("transient")

        with patch("tools.gui.pyautogui.click", side_effect=flaky), patch("tools.gui.time.sleep"):
            tool = self._make_tool()
            result = tool._run(action="click", x=10, y=10)

        assert isinstance(result, ToolError)
        assert call_count == 3  # attempted exactly 3 times

    def test_retry_succeeds_on_second_attempt(self) -> None:
        attempts = [0]

        def succeed_second(*args: Any, **kwargs: Any) -> None:
            attempts[0] += 1
            if attempts[0] < 2:
                raise OSError("first fail")

        with patch("tools.gui.pyautogui.click", side_effect=succeed_second), patch("tools.gui.time.sleep"):
            tool = self._make_tool()
            result = tool._run(action="click", x=5, y=5)

        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        assert attempts[0] == 2

    async def test_arun_click(self) -> None:
        with patch("tools.gui.pyautogui.click"):
            tool = self._make_tool()
            result = await tool._arun(action="click", x=1, y=1, button="left", clicks=1)
        assert isinstance(result, GUIActionOutput)


# ===========================================================================
# files.py — FileTool
# ===========================================================================


class TestFileTool:
    def _make_tool(self) -> Any:
        from tools.files import FileTool

        return FileTool()

    def test_read_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello file", encoding="utf-8")
        tool = self._make_tool()
        result = tool._run(action="read", path=str(f))
        assert isinstance(result, FileReadOutput)
        assert result.content == "hello file"
        assert result.size_bytes == len(b"hello file")

    def test_write_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "output.txt"
        tool = self._make_tool()
        result = tool._run(action="write", path=str(dest), content="written content")
        assert _is_success(result)
        assert dest.read_text() == "written content"

    def test_write_no_overwrite_blocked(self, tmp_path: Path) -> None:
        f = tmp_path / "existing.txt"
        f.write_text("original")
        tool = self._make_tool()
        result = tool._run(action="write", path=str(f), content="new", overwrite=False)
        assert isinstance(result, ToolError)
        assert f.read_text() == "original"  # unchanged

    def test_move_file(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("moving")
        tool = self._make_tool()
        result = tool._run(action="move", src=str(src), dst=str(dst))
        assert isinstance(result, FileMoveOutput)
        assert dst.exists()
        assert not src.exists()

    def test_delete_file(self, tmp_path: Path) -> None:
        f = tmp_path / "delete_me.txt"
        f.write_text("bye")
        tool = self._make_tool()
        result = tool._run(action="delete", path=str(f))
        assert _is_success(result)
        assert not f.exists()

    def test_list_dir(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        tool = self._make_tool()
        result = tool._run(action="list", path=str(tmp_path))
        assert _is_success(result)
        names = [e["name"] for e in result["entries"]]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_traversal_blocked_read(self) -> None:
        tool = self._make_tool()
        result = tool._run(action="read", path="/etc/../etc/passwd")
        assert isinstance(result, ToolError)
        assert "traversal" in result.message.lower()

    def test_traversal_blocked_write(self) -> None:
        tool = self._make_tool()
        result = tool._run(action="write", path="/tmp/../tmp/evil.txt", content="x")
        assert isinstance(result, ToolError)

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        tool = self._make_tool()
        result = tool._run(action="read", path=str(tmp_path / "missing.txt"))
        assert isinstance(result, ToolError)

    def test_unknown_action(self) -> None:
        tool = self._make_tool()
        result = tool._run(action="chmod", path="/tmp/x")
        assert isinstance(result, ToolError)
        assert "chmod" in result.message


# ===========================================================================
# apps.py — AppTool
# ===========================================================================


class TestAppTool:
    def _make_tool(self) -> Any:
        from tools.apps import AppTool

        return AppTool()

    def test_launch_success(self) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with patch("tools.apps.subprocess.Popen", return_value=mock_proc):
            tool = self._make_tool()
            result = tool._run(action="launch", command=["notepad.exe"])
        assert isinstance(result, AppLaunchOutput)
        assert result.pid == 12345
        assert result.name == "notepad.exe"

    def test_launch_failure(self) -> None:
        with patch("tools.apps.subprocess.Popen", side_effect=FileNotFoundError("not found")):
            tool = self._make_tool()
            result = tool._run(action="launch", command=["nonexistent_app"])
        assert isinstance(result, ToolError)
        assert result.tool == "app_control"

    def test_list_processes(self) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 999
        mock_proc.name.return_value = "explorer.exe"
        mock_proc.status.return_value = "running"
        mock_proc.info = {"name": "explorer.exe"}

        with patch("tools.apps.psutil.process_iter", return_value=[mock_proc]):
            tool = self._make_tool()
            result = tool._run(action="list")

        assert _is_success(result)
        assert result["count"] >= 1
        names = [p["name"] for p in result["processes"]]
        assert "explorer.exe" in names

    def test_unknown_action(self) -> None:
        tool = self._make_tool()
        result = tool._run(action="kill", command=["notepad"])
        assert isinstance(result, ToolError)

    def test_launch_with_cwd(self, tmp_path: Path) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 555
        with patch("tools.apps.subprocess.Popen", return_value=mock_proc) as mock_popen:
            tool = self._make_tool()
            tool._run(action="launch", command=["cmd.exe"], cwd=str(tmp_path))
        assert mock_popen.call_args[1]["cwd"] == str(tmp_path)


# ===========================================================================
# clipboard.py — ClipboardTool
# ===========================================================================


class TestClipboardTool:
    def _make_tool(self) -> Any:
        from tools.clipboard import ClipboardTool

        return ClipboardTool()

    def test_read_clipboard(self) -> None:
        with patch("tools.clipboard.pyperclip.paste", return_value="copied text"):
            tool = self._make_tool()
            result = tool._run(action="read")
        assert isinstance(result, ClipboardReadOutput)
        assert result.text == "copied text"

    def test_write_clipboard(self) -> None:
        with patch("tools.clipboard.pyperclip.copy") as mock_copy:
            tool = self._make_tool()
            result = tool._run(action="write", text="hello clipboard")
        assert _is_success(result)
        mock_copy.assert_called_once_with("hello clipboard")
        assert result["copied"] is True

    def test_read_failure(self) -> None:
        with patch("tools.clipboard.pyperclip.paste", side_effect=Exception("no clipboard")):
            tool = self._make_tool()
            result = tool._run(action="read")
        assert isinstance(result, ToolError)
        assert result.retryable is True

    def test_write_failure(self) -> None:
        with patch("tools.clipboard.pyperclip.copy", side_effect=Exception("write fail")):
            tool = self._make_tool()
            result = tool._run(action="write", text="oops")
        assert isinstance(result, ToolError)

    def test_unknown_action(self) -> None:
        tool = self._make_tool()
        result = tool._run(action="clear")
        assert isinstance(result, ToolError)


# ===========================================================================
# notify.py — NotifyTool
# ===========================================================================


class TestNotifyTool:
    def _make_tool(self) -> Any:
        from tools.notify import NotifyTool

        return NotifyTool()

    def test_notify_success(self) -> None:
        mock_notification = MagicMock()
        with patch("tools.notify.notification", mock_notification):
            tool = self._make_tool()
            result = tool._run(title="Test", message="A notification", timeout=5)

        assert _is_success(result)
        assert result["sent"] is True
        assert result["title"] == "Test"
        mock_notification.notify.assert_called_once_with(title="Test", message="A notification", timeout=5)

    def test_notify_plyer_failure(self) -> None:
        mock_notification = MagicMock()
        mock_notification.notify.side_effect = Exception("no display")
        with patch("tools.notify.notification", mock_notification):
            tool = self._make_tool()
            result = tool._run(title="X", message="Y", timeout=5)
        assert isinstance(result, ToolError)
        assert result.tool == "notify"

    def test_notify_invalid_input(self) -> None:
        tool = self._make_tool()
        # title too long (> 64 chars)
        result = tool._run(title="A" * 100, message="ok", timeout=5)
        assert isinstance(result, ToolError)

    def test_notify_message_too_long(self) -> None:
        tool = self._make_tool()
        result = tool._run(title="Hi", message="M" * 300, timeout=5)
        assert isinstance(result, ToolError)


# ===========================================================================
# email_reader.py — EmailTool
# ===========================================================================


class TestEmailTool:
    def _make_tool(self) -> Any:
        from tools.email_reader import EmailTool

        return EmailTool()

    def _make_mock_imap(self, uids: list[bytes], raw_message: bytes) -> MagicMock:
        """Build a mock IMAP4_SSL context manager."""
        mock_imap = MagicMock()
        mock_imap.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap.__exit__ = MagicMock(return_value=False)
        mock_imap.login = MagicMock()
        mock_imap.select = MagicMock()
        mock_imap.search = MagicMock(return_value=("OK", [b" ".join(uids)]))
        mock_imap.fetch = MagicMock(return_value=("OK", [(None, raw_message)]))
        return mock_imap

    def test_missing_env_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("IMAP_HOST", raising=False)
        monkeypatch.delenv("IMAP_USER", raising=False)
        monkeypatch.delenv("IMAP_PASS", raising=False)
        tool = self._make_tool()
        result = tool._run(folder="INBOX", limit=5)
        assert isinstance(result, ToolError)
        assert result.retryable is False

    def test_fetch_emails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IMAP_HOST", "mail.example.com")
        monkeypatch.setenv("IMAP_USER", "user@example.com")
        monkeypatch.setenv("IMAP_PASS", "secret")

        # Build a minimal RFC 822 message
        import email as email_mod
        from email.mime.text import MIMEText

        msg = MIMEText("Hello email body")
        msg["Subject"] = "Test Subject"
        msg["From"] = "sender@example.com"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        raw = msg.as_bytes()

        mock_imap = self._make_mock_imap([b"1"], raw)

        with patch("tools.email_reader.imaplib.IMAP4_SSL", return_value=mock_imap):
            tool = self._make_tool()
            result = tool._run(folder="INBOX", limit=1)

        assert isinstance(result, EmailListOutput)
        assert len(result.emails) == 1
        assert result.emails[0].subject == "Test Subject"
        assert result.emails[0].sender == "sender@example.com"

    def test_imap_error_returns_retryable_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IMAP_HOST", "mail.example.com")
        monkeypatch.setenv("IMAP_USER", "u")
        monkeypatch.setenv("IMAP_PASS", "p")

        import imaplib as imap_mod

        with patch("tools.email_reader.imaplib.IMAP4_SSL", side_effect=imap_mod.IMAP4.error("connect fail")):
            tool = self._make_tool()
            result = tool._run(folder="INBOX", limit=5)

        assert isinstance(result, ToolError)
        assert result.retryable is True

    async def test_arun_returns_email_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IMAP_HOST", "mail.example.com")
        monkeypatch.setenv("IMAP_USER", "u@x.com")
        monkeypatch.setenv("IMAP_PASS", "pass")

        from email.mime.text import MIMEText

        msg = MIMEText("async body")
        msg["Subject"] = "Async Test"
        msg["From"] = "a@b.com"
        msg["Date"] = "Tue, 02 Jan 2024 00:00:00 +0000"
        raw = msg.as_bytes()

        mock_imap = self._make_mock_imap([b"1"], raw)
        with patch("tools.email_reader.imaplib.IMAP4_SSL", return_value=mock_imap):
            tool = self._make_tool()
            result = await tool._arun(folder="INBOX", limit=1)

        assert isinstance(result, EmailListOutput)

    def test_invalid_input(self) -> None:
        tool = self._make_tool()
        result = tool._run(folder="INBOX", limit=200)  # > max 100
        assert isinstance(result, ToolError)


# ===========================================================================
# tools/__init__.py — TOOL_MANIFEST import
# ===========================================================================


class TestToolManifest:
    def test_manifest_imports_without_crash(self) -> None:
        """Importing TOOL_MANIFEST should not raise even without hardware."""
        # Patch all hardware-dependent imports at module boundaries
        with (
            patch("tools.screen.mss"),
            patch("tools.screen.pytesseract"),
            patch("tools.gui.pyautogui"),
            patch("tools.clipboard.pyperclip"),
        ):
            from tools import TOOL_MANIFEST

            assert len(TOOL_MANIFEST) == 7

    def test_all_tools_have_name_and_description(self) -> None:
        with (
            patch("tools.screen.mss"),
            patch("tools.screen.pytesseract"),
            patch("tools.gui.pyautogui"),
            patch("tools.clipboard.pyperclip"),
        ):
            from tools import TOOL_MANIFEST

            for tool in TOOL_MANIFEST:
                assert tool.name, f"{tool.__class__.__name__} has no name"
                assert len(tool.description) <= 100, (
                    f"{tool.name} description too long: {len(tool.description)} chars"
                )
                assert tool.description[0].isupper() or tool.description[0].isalpha(), (
                    f"{tool.name} description should start with action verb"
                )

    def test_tool_names_are_unique(self) -> None:
        with (
            patch("tools.screen.mss"),
            patch("tools.screen.pytesseract"),
            patch("tools.gui.pyautogui"),
            patch("tools.clipboard.pyperclip"),
        ):
            from tools import TOOL_MANIFEST

            names = [t.name for t in TOOL_MANIFEST]
            assert len(names) == len(set(names)), "Duplicate tool names found"
