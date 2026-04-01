"""Automation pipeline tests — 5 test cases covering the full observe-act-verify loop.

These tests mock all external I/O (screen, pyautogui, pyperclip, subprocess) so
they run without a display or any applications installed.  They verify that:

  1. GUITool dispatches every action correctly (click, type, scroll, hotkey, wait)
  2. Type uses clipboard paste (not typewrite) — Electron-app compatible
  3. Wait action pauses for the requested duration
  4. TaskPlanner decomposes a multi-step instruction into numbered steps
  5. The enriched prompt passed to the orchestrator contains both the original
     instruction and the plan
  6. screen_capture._arun runs in an executor (non-blocking)
  7. AppTool launches a process and returns pid+name
  8. The full instruction→plan→execute pipeline flows end-to-end

Test case mapping to real user scenarios:
  TC-1  Open Spotify and search for a song     (multi-app search)
  TC-2  Open Notepad and type a message        (text input)
  TC-3  Take a screenshot and read screen      (OCR / observe loop)
  TC-4  Press Ctrl+C on selected text          (hotkey)
  TC-5  Full pipeline: plan → enriched prompt  (orchestrator wiring)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from schemas.models import (
    AppLaunchOutput,
    GUIActionInput,
    GUIActionOutput,
    ScreenCaptureOutput,
    ToolError,
)


# ===========================================================================
# TC-1: Open Spotify and search for a song
# (Tests: app launch → wait → click → type via paste → hotkey)
# ===========================================================================


class TestSpotifySearchFlow:
    """Simulates: launch Spotify → wait → click search → type song → press Enter."""

    def _make_gui(self) -> Any:
        from tools.gui import GUITool

        return GUITool()

    def _make_app(self) -> Any:
        from tools.apps import AppTool

        return AppTool()

    def test_launch_spotify(self) -> None:
        """app_control launch returns a valid pid and name."""
        tool = self._make_app()
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        with patch("subprocess.Popen", return_value=mock_proc):
            result = tool._run(action="launch", command=["Spotify.exe"])
        assert isinstance(result, AppLaunchOutput)
        assert result.pid == 9999

    def test_wait_after_launch(self) -> None:
        """gui_action wait pauses for the requested number of seconds."""
        tool = self._make_gui()
        start = time.monotonic()
        with patch("time.sleep") as mock_sleep:
            result = tool._run(action="wait", seconds=3.0)
        mock_sleep.assert_called_once_with(3.0)
        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        assert "3.0s" in result.message

    def test_click_search_box(self) -> None:
        """gui_action click calls pyautogui.click at the given coordinates."""
        tool = self._make_gui()
        with patch("pyautogui.click") as mock_click:
            result = tool._run(action="click", x=640, y=60)
        mock_click.assert_called_once_with(640, 60, clicks=1, button="left")
        assert isinstance(result, GUIActionOutput)
        assert result.success is True

    def test_type_song_name_uses_clipboard_paste(self) -> None:
        """gui_action type uses pyperclip.copy + ctrl+v (NOT typewrite)."""
        tool = self._make_gui()
        with (
            patch("pyperclip.copy") as mock_copy,
            patch("pyperclip.paste", return_value=""),
            patch("pyautogui.hotkey") as mock_hotkey,
            patch("time.sleep"),
        ):
            result = tool._run(action="type", text="Eko by yuele")
        # Must copy text to clipboard
        mock_copy.assert_any_call("Eko by yuele")
        # Must use ctrl+v paste — NOT typewrite
        mock_hotkey.assert_any_call("ctrl", "v")
        assert isinstance(result, GUIActionOutput)
        assert result.success is True
        assert "paste" in result.message

    def test_press_enter_to_search(self) -> None:
        """gui_action hotkey with ['return'] presses Enter."""
        tool = self._make_gui()
        with patch("pyautogui.hotkey") as mock_hotkey:
            result = tool._run(action="hotkey", keys=["return"])
        mock_hotkey.assert_called_once_with("return")
        assert isinstance(result, GUIActionOutput)
        assert result.success is True


# ===========================================================================
# TC-2: Open Notepad and type a message
# (Tests: type restores original clipboard, clear all before typing)
# ===========================================================================


class TestNotepadTypeFlow:
    """Simulates: open Notepad → click text area → select all → type message."""

    def _make_gui(self) -> Any:
        from tools.gui import GUITool

        return GUITool()

    def test_type_restores_clipboard(self) -> None:
        """After typing, the original clipboard content is restored."""
        tool = self._make_gui()
        clipboard_state: list[str] = []

        def fake_copy(text: str) -> None:
            clipboard_state.append(text)

        with (
            patch("pyperclip.paste", return_value="original clipboard"),
            patch("pyperclip.copy", side_effect=fake_copy),
            patch("pyautogui.hotkey"),
            patch("time.sleep"),
        ):
            tool._run(action="type", text="Hello World")

        # First call sets our text, last call restores original
        assert clipboard_state[0] == "Hello World"
        assert clipboard_state[-1] == "original clipboard"

    def test_select_all_before_type(self) -> None:
        """Pressing ctrl+a selects all existing text before typing."""
        tool = self._make_gui()
        with patch("pyautogui.hotkey") as mock_hotkey:
            result = tool._run(action="hotkey", keys=["ctrl", "a"])
        mock_hotkey.assert_called_once_with("ctrl", "a")
        assert result.success is True  # type: ignore[union-attr]

    def test_type_empty_string_returns_tool_error(self) -> None:
        """Typing an empty string: GUITypeInput rejects it (min_length=1)."""
        from schemas.models import GUITypeInput

        with pytest.raises(Exception):
            GUITypeInput(text="")

    def test_double_click_to_select_word(self) -> None:
        """gui_action click with clicks=2 performs a double-click."""
        tool = self._make_gui()
        with patch("pyautogui.click") as mock_click:
            result = tool._run(action="click", x=300, y=200, clicks=2)
        mock_click.assert_called_once_with(300, 200, clicks=2, button="left")
        assert result.success is True  # type: ignore[union-attr]


# ===========================================================================
# TC-3: Observe the screen and verify content
# (Tests: screen_capture returns OCR text, _arun uses executor)
# ===========================================================================


class TestScreenObserveLoop:
    """Simulates the observe → act → verify loop via screen_capture."""

    def _make_tool(self) -> Any:
        from tools.screen import ScreenTool

        return ScreenTool()

    def test_full_screen_capture_returns_text(self) -> None:
        """screen_capture with no region runs OCR and returns extracted text."""
        tool = self._make_tool()
        with (
            patch("mss.mss") as mock_mss,
            patch("pytesseract.image_to_string", return_value="  Spotify  Search  "),
            patch("PIL.Image.frombytes") as mock_img,
        ):
            mock_ctx = MagicMock()
            mock_mss.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_mss.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
            mock_ctx.grab.return_value = MagicMock(size=(1920, 1080), bgra=b"")
            mock_img.return_value = MagicMock()
            result = tool._run()
        assert isinstance(result, ScreenCaptureOutput)
        assert "Spotify" in result.text

    def test_region_capture_passes_correct_monitor(self) -> None:
        """Providing a region passes left/top/width/height to mss."""
        tool = self._make_tool()
        captured_monitor: dict = {}

        with (
            patch("mss.mss") as mock_mss,
            patch("pytesseract.image_to_string", return_value="Search bar"),
            patch("PIL.Image.frombytes") as mock_img,
        ):
            mock_ctx = MagicMock()
            mock_mss.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_mss.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.grab.side_effect = lambda m: (captured_monitor.update(m) or MagicMock(size=(100, 50), bgra=b""))
            mock_img.return_value = MagicMock()
            tool._run(region=(100, 50, 400, 200))

        assert captured_monitor.get("left") == 100
        assert captured_monitor.get("top") == 50
        assert captured_monitor.get("width") == 400
        assert captured_monitor.get("height") == 200

    @pytest.mark.asyncio
    async def test_arun_uses_executor(self) -> None:
        """screen_capture._arun offloads work to a thread executor (non-blocking)."""
        tool = self._make_tool()
        called_in_executor = []

        async def fake_run_in_executor(executor: Any, fn: Any) -> Any:
            called_in_executor.append(True)
            return fn()

        fake_result = ScreenCaptureOutput(text="Spotify is open")

        with patch.object(tool, "_run", return_value=fake_result):
            loop = asyncio.get_event_loop()
            with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
                result = await tool._arun()

        assert called_in_executor, "_arun must use run_in_executor"
        assert result.text == "Spotify is open"  # type: ignore[union-attr]


# ===========================================================================
# TC-4: Keyboard shortcuts (copy, paste, undo, find)
# (Tests: hotkey with multi-key combos, scroll with negative direction)
# ===========================================================================


class TestKeyboardAndScroll:
    """Tests hotkey combos and scroll direction."""

    def _make_gui(self) -> Any:
        from tools.gui import GUITool

        return GUITool()

    def test_ctrl_c_copy(self) -> None:
        """Ctrl+C sends a copy hotkey."""
        tool = self._make_gui()
        with patch("pyautogui.hotkey") as mock_hotkey:
            result = tool._run(action="hotkey", keys=["ctrl", "c"])
        mock_hotkey.assert_called_once_with("ctrl", "c")
        assert result.success is True  # type: ignore[union-attr]

    def test_ctrl_f_find(self) -> None:
        """Ctrl+F opens find dialog."""
        tool = self._make_gui()
        with patch("pyautogui.hotkey") as mock_hotkey:
            result = tool._run(action="hotkey", keys=["ctrl", "f"])
        mock_hotkey.assert_called_once_with("ctrl", "f")
        assert result.success is True  # type: ignore[union-attr]

    def test_scroll_down_negative(self) -> None:
        """Negative scroll value scrolls down."""
        tool = self._make_gui()
        with patch("pyautogui.scroll") as mock_scroll:
            result = tool._run(action="scroll", x=960, y=540, clicks=-3)
        mock_scroll.assert_called_once_with(-3, x=960, y=540)
        assert result.success is True  # type: ignore[union-attr]

    def test_scroll_up_positive(self) -> None:
        """Positive scroll value scrolls up."""
        tool = self._make_gui()
        with patch("pyautogui.scroll") as mock_scroll:
            result = tool._run(action="scroll", x=960, y=540, clicks=5)
        mock_scroll.assert_called_once_with(5, x=960, y=540)
        assert result.success is True  # type: ignore[union-attr]

    def test_unknown_action_returns_tool_error(self) -> None:
        """Unrecognised action returns ToolError (does not raise)."""
        tool = self._make_gui()
        result = tool._run(action="fly")  # type: ignore[arg-type]
        assert isinstance(result, ToolError)
        assert "Unknown action" in result.message

    def test_wait_clamped_to_30s_max(self) -> None:
        """Wait of >30s is clamped to 30s."""
        tool = self._make_gui()
        with patch("time.sleep") as mock_sleep:
            result = tool._run(action="wait", seconds=99.0)
        mock_sleep.assert_called_once_with(30.0)
        assert result.success is True  # type: ignore[union-attr]

    def test_wait_clamped_minimum_01s(self) -> None:
        """Wait of 0s is clamped to 0.1s."""
        tool = self._make_gui()
        with patch("time.sleep") as mock_sleep:
            # seconds ge=0.1 enforced by schema — send via kwargs to bypass schema
            tool._wait(0.0)
        mock_sleep.assert_called_once_with(0.1)


# ===========================================================================
# TC-5: Full pipeline — plan → enriched prompt → orchestrator
# (Tests: planner → main._run_instruction enriched instruction format)
# ===========================================================================


class TestFullPipeline:
    """Tests the planning + execution wiring without Ollama."""

    @pytest.mark.asyncio
    async def test_planner_decomposes_spotify_task(self) -> None:
        """TaskPlanner breaks 'open Spotify and search for Eko' into ≥3 steps."""
        from core.planner import TaskPlanner

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content=(
                    "1. Launch Spotify\n"
                    "2. Wait 3 seconds for Spotify to open\n"
                    "3. Capture screen to find the search box\n"
                    "4. Click the search box\n"
                    "5. Type 'Eko by yuele'\n"
                    "6. Press Enter to search\n"
                )
            )
        )
        planner = TaskPlanner(mock_llm)
        steps = await planner.decompose("open Spotify and search for Eko by yuele")

        assert len(steps) >= 3
        assert any("Spotify" in s for s in steps)
        assert any("search" in s.lower() or "type" in s.lower() for s in steps)

    @pytest.mark.asyncio
    async def test_step_prompt_contains_task_and_screen_context(self) -> None:
        """STEP_PROMPT includes task, step number, description, and screen text."""
        from core.prompts import STEP_PROMPT

        prompt = STEP_PROMPT.format(
            task="open Spotify and search for Eko by yuele",
            step_num=4,
            total=6,
            step_desc="Click the search box",
            screen_text="Spotify Home Podcasts Search Library",
        )

        assert "open Spotify" in prompt
        assert "Step 4 of 6" in prompt
        assert "Click the search box" in prompt
        assert "Spotify Home Podcasts" in prompt
        # Must instruct single-step focus
        assert "only" in prompt.lower() or "only" in prompt
        # Must include verification instruction
        assert "screen_capture" in prompt

    @pytest.mark.asyncio
    async def test_planner_fallback_on_parse_failure(self) -> None:
        """If LLM returns unparseable output, planner falls back to [instruction]."""
        from core.planner import TaskPlanner

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="Sure! I'll help you with that task.")
        )
        planner = TaskPlanner(mock_llm)
        steps = await planner.decompose("do something")

        assert steps == ["do something"]

    @pytest.mark.asyncio
    async def test_planner_fallback_on_llm_error(self) -> None:
        """If planner throws, _run_instruction falls back to [instruction] and runs it."""
        import main as app_main

        calls: list[tuple[str, str]] = []  # (instr, thread_id)

        class _FakePlanner:
            async def decompose(self, instr: str) -> list[str]:
                raise RuntimeError("Ollama timed out")

        class _FakeOrchestrator:
            _llm = MagicMock()
            _tools: list = []

            async def run(self, instr: str, thread_id: str | None = None) -> AsyncIterator[str]:
                calls.append((instr, thread_id or ""))
                yield "Step 1 done: launched Spotify."

        class _FakeOverlay:
            def on_step_update(self, *a: Any) -> None:
                pass

            def on_token(self, t: str) -> None:
                pass

        class _FakeSession:
            def __call__(self) -> Any:
                return self

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *a: Any) -> None:
                pass

            async def commit(self) -> None:
                pass

        with patch("core.planner.TaskPlanner", return_value=_FakePlanner()):
            with patch("tools.screen.capture_screen_text", return_value="Desktop"):
                with patch("db.crud.create_execution", new_callable=AsyncMock):
                    await app_main._run_instruction(
                        "open Spotify and search for Eko by yuele",
                        _FakeOverlay(),
                        _FakeOrchestrator(),
                        _FakeSession(),
                    )

        # Orchestrator must have been called exactly once (one fallback step)
        assert len(calls) == 1
        instr, tid = calls[0]
        # The fallback step prompt contains the original task
        assert "Spotify" in instr
        # Each step uses a unique thread_id (not the shared session thread)
        assert tid != "" and "_step_" in tid
