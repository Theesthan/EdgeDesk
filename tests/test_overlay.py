"""Tests for ui/overlay.py and core/hotkey.py.

Import / attribute tests run without a display.
Widget instantiation tests require PyQt6 and a working display; they are
skipped automatically when those conditions are not met.
"""

from __future__ import annotations

import sys

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app():
    """Return the running QApplication or create one.  Returns None on failure."""
    try:
        from PyQt6.QtWidgets import QApplication

        return QApplication.instance() or QApplication(sys.argv[:1])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ui/overlay module — import / attribute tests (no display needed)
# ---------------------------------------------------------------------------


def test_overlay_module_importable() -> None:
    try:
        import ui.overlay  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_window_has_required_attributes() -> None:
    try:
        from ui.overlay import OverlayWindow
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(OverlayWindow, "instruction_submitted")
    assert hasattr(OverlayWindow, "on_token")
    assert hasattr(OverlayWindow, "on_step_update")
    assert hasattr(OverlayWindow, "show_overlay")
    assert hasattr(OverlayWindow, "dismiss")
    assert OverlayWindow._WIDTH == 680


def test_input_bar_has_focus_property() -> None:
    try:
        from ui.overlay import InputBar
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(InputBar, "focus_t")


def test_step_log_area_has_required_methods() -> None:
    try:
        from ui.overlay import StepLogArea
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(StepLogArea, "add_step_pill")
    assert hasattr(StepLogArea, "get_step_pill")
    assert hasattr(StepLogArea, "clear_steps")
    assert StepLogArea._MAX_H == 400


def test_apply_dwm_blur_is_callable() -> None:
    try:
        from ui.overlay import _apply_dwm_blur
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert callable(_apply_dwm_blur)


def test_apply_dwm_blur_noop_on_non_windows() -> None:
    """_apply_dwm_blur must not raise on non-Windows platforms."""
    try:
        from unittest.mock import MagicMock

        from ui.overlay import _apply_dwm_blur
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")

    if sys.platform == "win32":
        pytest.skip("Windows-specific no-op test skipped on Windows")

    mock_widget = MagicMock()
    _apply_dwm_blur(mock_widget)  # must not raise


# ---------------------------------------------------------------------------
# core/hotkey module — import / attribute tests (no display needed)
# ---------------------------------------------------------------------------


def test_hotkey_manager_importable() -> None:
    try:
        from core.hotkey import HotkeyManager  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"keyboard or PyQt6 not available: {exc}")


def test_hotkey_manager_has_required_attributes() -> None:
    try:
        from core.hotkey import HotkeyManager
    except ImportError as exc:
        pytest.skip(f"keyboard or PyQt6 not available: {exc}")
    assert hasattr(HotkeyManager, "register")
    assert hasattr(HotkeyManager, "unregister")
    assert hasattr(HotkeyManager, "hotkey_triggered")
    assert hasattr(HotkeyManager, "_fire")


# ---------------------------------------------------------------------------
# InputBar — functional tests (require display)
# ---------------------------------------------------------------------------


def test_input_bar_instantiation() -> None:
    try:
        from ui.overlay import InputBar

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        bar = InputBar()
        assert bar.placeholderText() == "Ask EdgeDesk anything..."
        assert bar.height() == 48
        bar.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_input_bar_focus_t_initial_zero() -> None:
    try:
        from ui.overlay import InputBar

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        bar = InputBar()
        assert bar.focus_t == pytest.approx(0.0)
        bar.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_input_bar_focus_t_setter() -> None:
    try:
        from ui.overlay import InputBar

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        bar = InputBar()
        bar.focus_t = 0.5
        assert bar.focus_t == pytest.approx(0.5)
        bar.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


# ---------------------------------------------------------------------------
# StepLogArea — functional tests (require display)
# ---------------------------------------------------------------------------


def test_step_log_area_initially_collapsed() -> None:
    try:
        from ui.overlay import StepLogArea

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        area = StepLogArea()
        assert area.maximumHeight() == 0
        area.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_step_log_area_add_and_get() -> None:
    try:
        from ui.overlay import StepLogArea

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        area = StepLogArea()
        pill = area.add_step_pill("s1", "Test step", "pending")
        assert area.get_step_pill("s1") is pill
        assert area.get_step_pill("nonexistent") is None
        area.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_step_log_area_add_opens_area() -> None:
    try:
        from ui.overlay import StepLogArea

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        area = StepLogArea()
        area.add_step_pill("s1", "Step 1", "running")
        # Animation target is MAX_H; maximumHeight will be > 0 once set
        assert area.maximumHeight() > 0 or area._height_anim.endValue() == StepLogArea._MAX_H
        area.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_step_log_area_clear() -> None:
    try:
        from ui.overlay import StepLogArea

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        area = StepLogArea()
        area.add_step_pill("s1", "Step 1", "done")
        area.add_step_pill("s2", "Step 2", "running")
        area.clear_steps()
        assert area.get_step_pill("s1") is None
        assert area.get_step_pill("s2") is None
        assert area.maximumHeight() == 0
        area.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


# ---------------------------------------------------------------------------
# OverlayWindow — functional tests (require display)
# ---------------------------------------------------------------------------


def test_overlay_window_instantiation() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        assert not overlay.isVisible()
        assert overlay.width() == OverlayWindow._WIDTH
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_instruction_submitted_on_return() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        received: list[str] = []
        overlay.instruction_submitted.connect(received.append)
        overlay._input.setText("hello world")
        overlay._on_return()
        assert received == ["hello world"]
        assert overlay._input.text() == ""
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_empty_return_not_emitted() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        received: list[str] = []
        overlay.instruction_submitted.connect(received.append)
        overlay._input.setText("   ")
        overlay._on_return()
        assert received == []
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_on_step_update_creates_pill() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        overlay.on_step_update("s1", "running", "Scanning screen")
        pill = overlay._steps.get_step_pill("s1")
        assert pill is not None
        assert overlay._current_step_id == "s1"
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_on_step_update_done_clears_current() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        overlay.on_step_update("s1", "running", "Scanning screen")
        overlay.on_step_update("s1", "done", "Done scanning")
        assert overlay._current_step_id is None
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_on_step_update_updates_existing_pill() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        overlay.on_step_update("s1", "running", "Start")
        overlay.on_step_update("s1", "done", "Finished")
        pill = overlay._steps.get_step_pill("s1")
        assert pill is not None
        assert pill._text_lbl.text() == "Finished"
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_on_token_creates_auto_pill() -> None:
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        overlay.on_token("Hello ")
        overlay.on_token("world")
        pill = overlay._steps.get_step_pill("step_auto")
        assert pill is not None
        assert "Hello " in pill._text_lbl.text()
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_overlay_dismiss_hides_when_not_visible() -> None:
    """dismiss() on a hidden overlay must be a no-op (no crash)."""
    try:
        from ui.overlay import OverlayWindow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        overlay = OverlayWindow()
        assert not overlay.isVisible()
        overlay.dismiss()  # must not raise
        overlay.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


# ---------------------------------------------------------------------------
# HotkeyManager — functional tests (require display)
# ---------------------------------------------------------------------------


def test_hotkey_manager_instantiation() -> None:
    try:
        from core.hotkey import HotkeyManager

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        mgr = HotkeyManager("alt+space")
        assert mgr._hotkey == "alt+space"
        assert not mgr._registered
        mgr.deleteLater()
    except ImportError as exc:
        pytest.skip(f"keyboard or PyQt6 not available: {exc}")


def test_hotkey_manager_unregister_when_not_registered() -> None:
    """unregister() before register() must be a no-op."""
    try:
        from core.hotkey import HotkeyManager

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        mgr = HotkeyManager("alt+space")
        mgr.unregister()  # must not raise
        assert not mgr._registered
        mgr.deleteLater()
    except ImportError as exc:
        pytest.skip(f"keyboard or PyQt6 not available: {exc}")
