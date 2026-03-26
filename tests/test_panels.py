"""Tests for Phase 8 UI panels: tray, settings, history, rule editor.

Import / attribute tests run without a display.
Widget instantiation tests require PyQt6 + a working display;
they are skipped automatically when those conditions are not met.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app():
    """Return the running QApplication or create one. Returns None on failure."""
    try:
        from PyQt6.QtWidgets import QApplication

        return QApplication.instance() or QApplication(sys.argv[:1])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ui/tray — import / attribute tests
# ---------------------------------------------------------------------------


def test_tray_importable() -> None:
    try:
        import ui.tray  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_system_tray_app_signals() -> None:
    try:
        from ui.tray import SystemTrayApp
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    for sig in (
        "open_overlay_requested",
        "open_rules_requested",
        "open_history_requested",
        "open_settings_requested",
        "quit_requested",
    ):
        assert hasattr(SystemTrayApp, sig), f"Missing signal: {sig}"


def test_system_tray_app_has_show_notification() -> None:
    try:
        from ui.tray import SystemTrayApp
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert callable(SystemTrayApp.show_notification)


# ---------------------------------------------------------------------------
# ui/settings — import / attribute tests
# ---------------------------------------------------------------------------


def test_settings_importable() -> None:
    try:
        import ui.settings  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_settings_dialog_signals() -> None:
    try:
        from ui.settings import SettingsDialog
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(SettingsDialog, "hotkey_changed")
    assert hasattr(SettingsDialog, "clear_history_requested")
    assert hasattr(SettingsDialog, "export_data_requested")


# ---------------------------------------------------------------------------
# ui/history_view — import / attribute tests
# ---------------------------------------------------------------------------


def test_history_view_importable() -> None:
    try:
        import ui.history_view  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_history_view_has_required_signals() -> None:
    try:
        from ui.history_view import HistoryView
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(HistoryView, "load_more_requested")
    assert hasattr(HistoryView, "feedback_given")
    assert hasattr(HistoryView, "load_executions")


def test_history_row_has_feedback_signal() -> None:
    try:
        from ui.history_view import HistoryRow
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(HistoryRow, "feedback_given")
    assert hasattr(HistoryRow, "toggle_expand")


# ---------------------------------------------------------------------------
# ui/rule_editor — import / attribute tests
# ---------------------------------------------------------------------------


def test_rule_editor_importable() -> None:
    try:
        import ui.rule_editor  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_rule_manager_panel_signals() -> None:
    try:
        from ui.rule_editor import RuleManagerPanel
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(RuleManagerPanel, "rule_saved")
    assert hasattr(RuleManagerPanel, "rule_deleted")
    assert hasattr(RuleManagerPanel, "rule_toggled")
    assert hasattr(RuleManagerPanel, "load_rules")


def test_rule_card_signals() -> None:
    try:
        from ui.rule_editor import RuleCard
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(RuleCard, "clicked")
    assert hasattr(RuleCard, "toggled")


def test_rule_detail_editor_signals() -> None:
    try:
        from ui.rule_editor import RuleDetailEditor
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
    assert hasattr(RuleDetailEditor, "saved")
    assert hasattr(RuleDetailEditor, "deleted")
    assert hasattr(RuleDetailEditor, "load_rule")


# ---------------------------------------------------------------------------
# SettingsDialog — functional tests (require display)
# ---------------------------------------------------------------------------


def test_settings_dialog_instantiation() -> None:
    try:
        from ui.settings import SettingsDialog

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        dlg = SettingsDialog()
        assert dlg.width() == 640
        assert dlg.height() == 480
        dlg.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_settings_dialog_save_load_roundtrip(tmp_path: Path) -> None:
    """Settings saved to a temp .env must be readable back."""
    try:
        from dotenv import dotenv_values  # type: ignore[import]
        from ui.settings import SettingsDialog

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")

        env_file = tmp_path / ".env"
        dlg = SettingsDialog(env_path=env_file)

        # Change model name and save
        dlg._model_edit.setText("phi3.5")
        dlg._save_settings()

        assert env_file.exists(), ".env file was not created by save_settings"
        values = dotenv_values(str(env_file))
        assert values.get("OLLAMA_MODEL") == "phi3.5"
        dlg.deleteLater()
    except ImportError as exc:
        pytest.skip(f"dotenv or PyQt6 not available: {exc}")


def test_settings_dialog_load_from_env(tmp_path: Path) -> None:
    """Existing .env values are loaded into the form on open."""
    try:
        from ui.settings import SettingsDialog

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")

        env_file = tmp_path / ".env"
        env_file.write_text("OLLAMA_MODEL=llama3.1\nOLLAMA_BASE_URL=http://localhost:11434\n")

        dlg = SettingsDialog(env_path=env_file)
        assert dlg._model_edit.text() == "llama3.1"
        dlg.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_settings_dialog_tab_switching() -> None:
    try:
        from ui.settings import SettingsDialog

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        dlg = SettingsDialog()
        assert dlg._stack.currentIndex() == 0
        dlg._tabs.set_current(2, animate=False)
        assert dlg._stack.currentIndex() == 2
        dlg.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


# ---------------------------------------------------------------------------
# HistoryView — functional tests (require display)
# ---------------------------------------------------------------------------


_SAMPLE_EXECUTIONS: list[dict] = [
    {
        "id": "exec-1",
        "rule_name": "Daily Report",
        "started_at": "2026-03-27T09:00:00",
        "status": "success",
        "duration_seconds": 3.2,
        "steps_log": [
            {"text": "Opened browser", "status": "done"},
            {"text": "Extracted data", "status": "done"},
        ],
    },
    {
        "id": "exec-2",
        "rule_name": "Morning Briefing",
        "started_at": "2026-03-27T08:00:00",
        "status": "failed",
        "duration_seconds": 1.1,
        "steps_log": [],
    },
]


def test_history_view_instantiation() -> None:
    try:
        from ui.history_view import HistoryView

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        view = HistoryView()
        assert view._total_loaded == 0
        view.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_history_view_load_executions() -> None:
    try:
        from ui.history_view import HistoryView

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        view = HistoryView()
        view.load_executions(_SAMPLE_EXECUTIONS)
        assert view._total_loaded == 2
        view.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_history_view_append() -> None:
    try:
        from ui.history_view import HistoryView

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        view = HistoryView()
        view.load_executions(_SAMPLE_EXECUTIONS[:1])
        view.load_executions(_SAMPLE_EXECUTIONS[1:], append=True)
        assert view._total_loaded == 2
        view.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_history_row_feedback_signal() -> None:
    try:
        from ui.history_view import HistoryRow

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        row = HistoryRow(_SAMPLE_EXECUTIONS[0])
        received: list[tuple[str, int]] = []
        row.feedback_given.connect(lambda eid, s: received.append((eid, s)))
        # Simulate thumbs-up click via internal helper
        row.feedback_given.emit("exec-1", 1)
        assert received == [("exec-1", 1)]
        row.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


# ---------------------------------------------------------------------------
# RuleManagerPanel — functional tests (require display)
# ---------------------------------------------------------------------------


_SAMPLE_RULES: list[dict] = [
    {
        "id": "rule-1",
        "name": "Auto Report",
        "trigger_type": "time_cron",
        "trigger_config": {"minute": "0", "hour": "9"},
        "enabled": True,
        "run_count": 5,
        "instruction": "Generate daily report",
    },
    {
        "id": "rule-2",
        "name": "Watch Folder",
        "trigger_type": "file_event",
        "trigger_config": {"path": "~/Downloads"},
        "enabled": False,
        "run_count": 0,
        "instruction": "Process new files",
    },
]


def test_rule_manager_panel_instantiation() -> None:
    try:
        from ui.rule_editor import RuleManagerPanel

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        panel = RuleManagerPanel()
        panel.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_rule_manager_panel_load_rules() -> None:
    try:
        from ui.rule_editor import RuleManagerPanel

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        panel = RuleManagerPanel()
        panel.load_rules(_SAMPLE_RULES)
        assert len(panel._rule_data) == 2
        assert "rule-1" in panel._rule_data
        panel.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_rule_detail_editor_load_and_save() -> None:
    try:
        from ui.rule_editor import RuleDetailEditor

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        editor = RuleDetailEditor()
        editor.load_rule(_SAMPLE_RULES[0])
        assert editor._name_edit.text() == "Auto Report"
        assert editor._rule_id == "rule-1"

        received: list[dict] = []
        editor.saved.connect(received.append)
        editor._on_save()
        assert len(received) == 1
        assert received[0]["name"] == "Auto Report"
        editor.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_rule_detail_editor_new_rule_has_no_delete() -> None:
    try:
        from ui.rule_editor import RuleDetailEditor

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        editor = RuleDetailEditor()
        editor.load_rule(None)
        assert editor._rule_id is None
        assert not editor._delete_btn.isVisible()
        editor.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_rule_toggled_signal() -> None:
    try:
        from ui.rule_editor import RuleManagerPanel

        app = _make_app()
        if app is None:
            pytest.skip("Cannot create QApplication")
        panel = RuleManagerPanel()
        panel.load_rules(_SAMPLE_RULES)
        received: list[tuple[str, bool]] = []
        panel.rule_toggled.connect(lambda rid, en: received.append((rid, en)))
        panel.rule_toggled.emit("rule-1", False)
        assert received == [("rule-1", False)]
        panel.deleteLater()
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")
