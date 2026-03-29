"""EdgeDesk — Local AI agent for privacy-first desktop automation.

Phase 9 boot sequence: all subsystems wired together via qasync.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from dotenv import load_dotenv
from loguru import logger

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Boot EdgeDesk: initialise all subsystems and start the Qt event loop."""
    load_dotenv()
    logger.info("EdgeDesk starting…")

    # Qt / qasync imports are deferred so load_dotenv() runs first.
    import qasync  # type: ignore[import]
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.run_until_complete(_async_main(app))


# ---------------------------------------------------------------------------
# Async boot sequence
# ---------------------------------------------------------------------------


async def _async_main(app: Any) -> None:  # app: QApplication
    """Full boot: DB → VectorStore → LLM → Agent → Scheduler → UI."""

    # 1. Database ----------------------------------------------------------
    from db.session import get_session_factory, init_db

    await init_db()
    session_factory = get_session_factory()
    logger.info("Database ready")

    # 2. Vector store (non-fatal) -----------------------------------------
    vector_store = None
    try:
        from db.vector_store import VectorStore

        vector_store = VectorStore()
        logger.info("VectorStore loaded")
    except Exception as exc:
        logger.warning("VectorStore unavailable: {} — semantic search disabled", exc)

    # 3. Ollama health check (non-fatal) -----------------------------------
    from core.llm import build_llm, health_check

    ollama_ok = True
    try:
        await health_check()
        logger.info("Ollama health check passed")
    except ConnectionError as exc:
        logger.warning("Ollama unreachable: {} — LLM features degraded", exc)
        ollama_ok = False

    # 4. LLM + orchestrator -----------------------------------------------
    from core.agent import AgentOrchestrator
    from tools import TOOL_MANIFEST

    llm = build_llm()
    orchestrator = AgentOrchestrator(llm, TOOL_MANIFEST)

    # 5. Scheduler --------------------------------------------------------
    from scheduler.engine import SchedulerEngine

    scheduler = SchedulerEngine(session_factory, orchestrator)
    await scheduler.start()

    # 6. UI components ----------------------------------------------------
    from core.hotkey import HotkeyManager
    from ui.history_view import HistoryView
    from ui.overlay import OverlayWindow
    from ui.rule_editor import RuleManagerPanel
    from ui.tray import SystemTrayApp

    tray = SystemTrayApp()
    overlay = OverlayWindow()

    rule_win = _make_panel_window("EdgeDesk — Rules", 960, 640)
    rule_panel = RuleManagerPanel(rule_win)
    rule_win.layout().addWidget(rule_panel)  # type: ignore[union-attr]

    hist_win = _make_panel_window("EdgeDesk — History", 860, 640)
    hist_view = HistoryView(hist_win)
    hist_win.layout().addWidget(hist_view)  # type: ignore[union-attr]

    # 7. Hotkey -----------------------------------------------------------
    hotkey_mgr = HotkeyManager("alt+space")
    hotkey_mgr.hotkey_triggered.connect(overlay.show_overlay)
    hotkey_mgr.register()

    # 8. Wire signals -----------------------------------------------------
    tray.open_overlay_requested.connect(overlay.show_overlay)
    tray.open_rules_requested.connect(
        lambda: asyncio.ensure_future(_show_rules(rule_win, rule_panel, session_factory))
    )
    tray.open_history_requested.connect(
        lambda: asyncio.ensure_future(_show_history(hist_win, hist_view, session_factory, 0))
    )
    tray.open_settings_requested.connect(lambda: _show_settings(hotkey_mgr, session_factory))

    overlay.instruction_submitted.connect(
        lambda instr: asyncio.ensure_future(
            _run_instruction(instr, overlay, orchestrator, session_factory)
        )
    )

    rule_panel.rule_saved.connect(
        lambda data: asyncio.ensure_future(
            _on_rule_saved(data, session_factory, scheduler, vector_store)
        )
    )
    rule_panel.rule_deleted.connect(
        lambda rid: asyncio.ensure_future(_on_rule_deleted(rid, session_factory, scheduler))
    )
    rule_panel.rule_toggled.connect(
        lambda rid, en: asyncio.ensure_future(_on_rule_toggled(rid, en, session_factory, scheduler))
    )

    hist_view.feedback_given.connect(
        lambda eid, score: asyncio.ensure_future(_on_feedback(eid, score, session_factory))
    )
    hist_view.load_more_requested.connect(
        lambda offset: asyncio.ensure_future(
            _show_history(hist_win, hist_view, session_factory, offset, append=True)
        )
    )

    # 9. Show tray + startup notification ---------------------------------
    tray.show()
    if not ollama_ok:
        tray.show_notification(
            "EdgeDesk — Warning",
            "Ollama is not running. Start it with `ollama serve`.",
        )
    else:
        tray.show_notification("EdgeDesk", "Running. Press Alt+Space to start.")

    # 10. Wait for shutdown -----------------------------------------------
    shutdown_event: asyncio.Event = asyncio.Event()
    tray.quit_requested.connect(
        lambda: asyncio.ensure_future(_shutdown(scheduler, hotkey_mgr, shutdown_event))
    )
    await shutdown_event.wait()

    from PyQt6.QtWidgets import QApplication as _QApp

    _QApp.instance().quit()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _make_panel_window(title: str, w: int, h: int) -> Any:  # returns QWidget
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    win = QWidget(None, Qt.WindowType.Window)  # type: ignore[call-overload]
    win.setWindowTitle(title)
    win.resize(w, h)
    layout = QVBoxLayout(win)
    layout.setContentsMargins(0, 0, 0, 0)
    return win


def _show_settings(hotkey_mgr: Any, session_factory: Any) -> None:
    from ui.settings import SettingsDialog

    dlg = SettingsDialog()

    def _on_hotkey_changed(new_key: str) -> None:
        hotkey_mgr.unregister()  # type: ignore[attr-defined]
        hotkey_mgr._hotkey = new_key  # type: ignore[attr-defined]
        hotkey_mgr.register()  # type: ignore[attr-defined]

    def _on_clear_history() -> None:
        asyncio.ensure_future(_clear_history(session_factory))

    dlg.hotkey_changed.connect(_on_hotkey_changed)
    dlg.clear_history_requested.connect(_on_clear_history)
    dlg.show()


# ---------------------------------------------------------------------------
# Async data handlers
# ---------------------------------------------------------------------------


async def _show_rules(
    win: Any,
    panel: Any,
    session_factory: Any,
) -> None:
    from db.crud import list_rules

    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            rules = await list_rules(session)
        panel.load_rules(  # type: ignore[attr-defined]
            [
                {
                    "id": r.id,
                    "name": r.name,
                    "trigger_type": r.trigger_type,
                    "trigger_config": r.trigger_config,
                    "enabled": r.enabled,
                    "run_count": r.run_count,
                    "instruction": r.instruction,
                }
                for r in rules
            ]
        )
        win.show()  # type: ignore[attr-defined]
        win.raise_()  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error("Failed to load rules: {}", exc)


async def _show_history(
    win: Any,
    view: Any,
    session_factory: Any,
    offset: int,
    *,
    append: bool = False,
) -> None:
    from db.crud import get_rule, list_executions

    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            execs = await list_executions(session, limit=100, offset=offset)
            rule_ids = {e.rule_id for e in execs if e.rule_id}
            rule_names: dict[str, str] = {}
            for rid in rule_ids:
                rule = await get_rule(session, rid)
                if rule:
                    rule_names[rid] = rule.name

        exec_dicts = [
            {
                "id": e.id,
                "rule_name": rule_names.get(e.rule_id or "", "Manual"),
                "started_at": e.executed_at,
                "status": e.status or "failed",
                "duration_seconds": (e.duration_ms / 1000.0) if e.duration_ms else None,
                "steps_log": e.steps_log or [],
            }
            for e in execs
        ]
        view.load_executions(exec_dicts, append=append)  # type: ignore[attr-defined]
        if not append:
            win.show()  # type: ignore[attr-defined]
            win.raise_()  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error("Failed to load history: {}", exc)


async def _run_instruction(
    instruction: str,
    overlay: Any,
    orchestrator: Any,
    session_factory: Any,
) -> None:
    """Stream *instruction* through the agent and log the execution result."""
    from db.crud import create_execution

    start_ms = int(time.monotonic() * 1000)
    step_id = "agent_run"
    overlay.on_step_update(step_id, "running", "Thinking…")  # type: ignore[attr-defined]
    status = "failed"

    try:
        async for token in orchestrator.run(instruction):  # type: ignore[attr-defined]
            overlay.on_token(token)  # type: ignore[attr-defined]
        status = "success"
        overlay.on_step_update(step_id, "done", "Done")  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error("Instruction execution error: {}", exc)
        overlay.on_step_update(step_id, "failed", f"Error: {exc}")  # type: ignore[attr-defined]

    duration_ms = int(time.monotonic() * 1000) - start_ms
    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            await create_execution(
                session,
                instruction=instruction,
                status=status,
                duration_ms=duration_ms,
            )
            await session.commit()
    except Exception as exc:
        logger.error("Failed to log execution: {}", exc)


async def _on_rule_saved(
    data: dict,
    session_factory: Any,
    scheduler: Any,
    vector_store: Any,
) -> None:
    from db.crud import create_rule, update_rule

    rule_id: str | None = data.get("id")
    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            if rule_id:
                await update_rule(
                    session,
                    rule_id,
                    name=data.get("name", ""),
                    instruction=data.get("instruction"),
                    trigger_type=data.get("trigger_type"),
                    trigger_config=data.get("trigger_config"),
                )
            else:
                rule = await create_rule(
                    session,
                    name=data.get("name") or "Unnamed",
                    instruction=data.get("instruction"),
                    trigger_type=data.get("trigger_type"),
                    trigger_config=data.get("trigger_config"),
                )
                rule_id = rule.id
            await session.commit()

        if rule_id:
            await scheduler.reload_rule(rule_id)  # type: ignore[attr-defined]

        if vector_store is not None and rule_id:
            text = f"{data.get('name', '')} {data.get('instruction', '')}"
            vector_store.add_rule(rule_id, text)  # type: ignore[attr-defined]

        logger.info("Rule saved: {}", rule_id)
    except Exception as exc:
        logger.error("Failed to save rule: {}", exc)


async def _on_rule_deleted(
    rule_id: str,
    session_factory: Any,
    scheduler: Any,
) -> None:
    from db.crud import delete_rule

    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            await delete_rule(session, rule_id)
            await session.commit()
        await scheduler.reload_rule(rule_id)  # type: ignore[attr-defined]
        logger.info("Rule deleted: {}", rule_id)
    except Exception as exc:
        logger.error("Failed to delete rule: {}", exc)


async def _on_rule_toggled(
    rule_id: str,
    enabled: bool,
    session_factory: Any,
    scheduler: Any,
) -> None:
    from db.crud import update_rule

    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            await update_rule(session, rule_id, enabled=enabled)
            await session.commit()
        await scheduler.reload_rule(rule_id)  # type: ignore[attr-defined]
        logger.info("Rule {} toggled: enabled={}", rule_id, enabled)
    except Exception as exc:
        logger.error("Failed to toggle rule: {}", exc)


async def _on_feedback(
    execution_id: str,
    score: int,
    session_factory: Any,
) -> None:
    from db.crud import update_feedback

    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            await update_feedback(session, execution_id, score)
            await session.commit()
        logger.debug("Feedback recorded: exec={} score={}", execution_id, score)
    except Exception as exc:
        logger.error("Failed to record feedback: {}", exc)


async def _clear_history(session_factory: Any) -> None:
    from sqlalchemy import delete as sa_delete

    from db.models import Execution

    try:
        async with session_factory() as session:  # type: ignore[attr-defined]
            await session.execute(sa_delete(Execution))
            await session.commit()
        logger.info("Execution history cleared")
    except Exception as exc:
        logger.error("Failed to clear history: {}", exc)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


async def _shutdown(
    scheduler: Any,
    hotkey_mgr: Any,
    shutdown_event: asyncio.Event,
) -> None:
    logger.info("Shutting down EdgeDesk…")
    hotkey_mgr.unregister()  # type: ignore[attr-defined]
    await scheduler.stop()  # type: ignore[attr-defined]
    shutdown_event.set()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
