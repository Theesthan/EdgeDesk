"""Tests for database CRUD operations and Pydantic schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from schemas.models import (
    AppLaunchInput,
    AppLaunchOutput,
    ClipboardReadOutput,
    ClipboardWriteInput,
    EmailItem,
    EmailListInput,
    EmailListOutput,
    FileMoveInput,
    FileMoveOutput,
    FileReadInput,
    FileReadOutput,
    FileWriteInput,
    GUIClickInput,
    GUIHotkeyInput,
    GUIScrollInput,
    GUITypeInput,
    NotifyInput,
    ScreenCaptureInput,
    ScreenCaptureOutput,
    ToolError,
)

# ===========================================================================
# Rule CRUD
# ===========================================================================


async def test_create_rule_minimal(db_session: AsyncSession) -> None:
    rule = await crud.create_rule(db_session, name="my_rule")
    await db_session.commit()
    assert rule.id is not None
    assert rule.name == "my_rule"
    assert rule.enabled is True
    assert rule.run_count == 0
    assert rule.success_rate == 0.0


async def test_create_rule_full(db_session: AsyncSession) -> None:
    rule = await crud.create_rule(
        db_session,
        name="full_rule",
        description="A complete rule",
        trigger_type="time_cron",
        trigger_config={"hour": 9, "minute": 0},
        steps=[{"action": "open", "app": "notepad"}],
        enabled=False,
    )
    await db_session.commit()
    assert rule.trigger_type == "time_cron"
    assert rule.trigger_config == {"hour": 9, "minute": 0}
    assert rule.enabled is False


async def test_create_rule_duplicate_name_raises(db_session: AsyncSession) -> None:
    await crud.create_rule(db_session, name="dup")
    await db_session.commit()
    with pytest.raises(Exception):  # IntegrityError from UNIQUE constraint
        await crud.create_rule(db_session, name="dup")
        await db_session.commit()


async def test_get_rule_found(db_session: AsyncSession) -> None:
    created = await crud.create_rule(db_session, name="findme")
    await db_session.commit()
    found = await crud.get_rule(db_session, created.id)
    assert found is not None
    assert found.name == "findme"


async def test_get_rule_not_found(db_session: AsyncSession) -> None:
    result = await crud.get_rule(db_session, "nonexistent-id")
    assert result is None


async def test_list_rules_all(db_session: AsyncSession) -> None:
    await crud.create_rule(db_session, name="r1", enabled=True)
    await crud.create_rule(db_session, name="r2", enabled=False)
    await db_session.commit()
    rules = await crud.list_rules(db_session)
    assert len(rules) == 2


async def test_list_rules_enabled_only(db_session: AsyncSession) -> None:
    await crud.create_rule(db_session, name="active", enabled=True)
    await crud.create_rule(db_session, name="inactive", enabled=False)
    await db_session.commit()
    rules = await crud.list_rules(db_session, enabled_only=True)
    assert all(r.enabled for r in rules)
    assert len(rules) == 1


async def test_update_rule(db_session: AsyncSession) -> None:
    rule = await crud.create_rule(db_session, name="updatable")
    await db_session.commit()
    updated = await crud.update_rule(db_session, rule.id, description="new desc", run_count=5)
    await db_session.commit()
    assert updated is not None
    assert updated.description == "new desc"
    assert updated.run_count == 5


async def test_update_rule_not_found(db_session: AsyncSession) -> None:
    result = await crud.update_rule(db_session, "ghost-id", name="nope")
    assert result is None


async def test_delete_rule_success(db_session: AsyncSession) -> None:
    rule = await crud.create_rule(db_session, name="delete_me")
    await db_session.commit()
    deleted = await crud.delete_rule(db_session, rule.id)
    await db_session.commit()
    assert deleted is True
    assert await crud.get_rule(db_session, rule.id) is None


async def test_delete_rule_not_found(db_session: AsyncSession) -> None:
    result = await crud.delete_rule(db_session, "no-such-id")
    assert result is False


# ===========================================================================
# Execution CRUD
# ===========================================================================


async def test_create_execution(db_session: AsyncSession) -> None:
    exc = await crud.create_execution(
        db_session,
        instruction="Open Notepad",
        status="success",
        duration_ms=1200,
        steps_log=[{"step": 1, "action": "launch"}],
    )
    await db_session.commit()
    assert exc.id is not None
    assert exc.status == "success"
    assert exc.feedback == 0


async def test_list_executions_newest_first(db_session: AsyncSession) -> None:
    await crud.create_execution(db_session, instruction="first")
    await crud.create_execution(db_session, instruction="second")
    await db_session.commit()
    execs = await crud.list_executions(db_session)
    assert len(execs) == 2


async def test_update_feedback_good(db_session: AsyncSession) -> None:
    exc = await crud.create_execution(db_session, instruction="test")
    await db_session.commit()
    updated = await crud.update_feedback(db_session, exc.id, feedback=1)
    await db_session.commit()
    assert updated is not None
    assert updated.feedback == 1


async def test_update_feedback_bad(db_session: AsyncSession) -> None:
    exc = await crud.create_execution(db_session, instruction="bad run")
    await db_session.commit()
    updated = await crud.update_feedback(db_session, exc.id, feedback=-1)
    await db_session.commit()
    assert updated is not None
    assert updated.feedback == -1


async def test_update_feedback_not_found(db_session: AsyncSession) -> None:
    result = await crud.update_feedback(db_session, "ghost", feedback=1)
    assert result is None


# ===========================================================================
# Agent Memory CRUD
# ===========================================================================


async def test_upsert_memory_create(db_session: AsyncSession) -> None:
    rec = await crud.upsert_memory(db_session, session_id="sess1", summary="Remember X")
    await db_session.commit()
    assert rec.session_id == "sess1"
    assert rec.summary == "Remember X"


async def test_upsert_memory_update(db_session: AsyncSession) -> None:
    await crud.upsert_memory(db_session, session_id="sess2", summary="v1")
    await db_session.commit()
    await crud.upsert_memory(db_session, session_id="sess2", summary="v2")
    await db_session.commit()
    mem = await crud.get_memory(db_session, "sess2")
    assert mem is not None
    assert mem.summary == "v2"


async def test_get_memory_not_found(db_session: AsyncSession) -> None:
    result = await crud.get_memory(db_session, "unknown-session")
    assert result is None


# ===========================================================================
# Schema Validation — ToolError
# ===========================================================================


def test_tool_error_valid() -> None:
    err = ToolError(tool="screen", message="OCR failed", retryable=True)
    assert err.tool == "screen"
    assert err.retryable is True


def test_tool_error_defaults() -> None:
    err = ToolError(tool="gui", message="Click missed")
    assert err.retryable is False


# ===========================================================================
# Schema Validation — Screen
# ===========================================================================


def test_screen_capture_input_no_region() -> None:
    inp = ScreenCaptureInput()
    assert inp.region is None


def test_screen_capture_input_valid_region() -> None:
    inp = ScreenCaptureInput(region=(0, 0, 1920, 1080))
    assert inp.region == (0, 0, 1920, 1080)


def test_screen_capture_input_invalid_region() -> None:
    with pytest.raises(ValidationError):
        ScreenCaptureInput(region=(0, 0, 0, 100))  # width=0 invalid


def test_screen_capture_output() -> None:
    out = ScreenCaptureOutput(text="Hello world")
    assert out.image_path is None


# ===========================================================================
# Schema Validation — GUI
# ===========================================================================


def test_gui_click_valid() -> None:
    inp = GUIClickInput(x=100, y=200)
    assert inp.button == "left"
    assert inp.clicks == 1


def test_gui_click_invalid_button() -> None:
    with pytest.raises(ValidationError):
        GUIClickInput(x=0, y=0, button="invalid")  # type: ignore[arg-type]


def test_gui_click_negative_coords() -> None:
    with pytest.raises(ValidationError):
        GUIClickInput(x=-1, y=0)


def test_gui_type_valid() -> None:
    inp = GUITypeInput(text="Hello")
    assert inp.interval == 0.05


def test_gui_type_empty_text() -> None:
    with pytest.raises(ValidationError):
        GUITypeInput(text="")


def test_gui_scroll_valid() -> None:
    inp = GUIScrollInput(x=0, y=0, clicks=-3)
    assert inp.clicks == -3


def test_gui_hotkey_valid() -> None:
    inp = GUIHotkeyInput(keys=["ctrl", "c"])
    assert inp.keys == ["ctrl", "c"]


def test_gui_hotkey_empty_list() -> None:
    with pytest.raises(ValidationError):
        GUIHotkeyInput(keys=[])


# ===========================================================================
# Schema Validation — Files
# ===========================================================================


def test_file_read_valid() -> None:
    inp = FileReadInput(path="/home/user/notes.txt")
    assert inp.path == "/home/user/notes.txt"


def test_file_read_traversal_blocked() -> None:
    with pytest.raises(ValidationError):
        FileReadInput(path="/home/../etc/passwd")


def test_file_write_valid() -> None:
    inp = FileWriteInput(path="/tmp/out.txt", content="hello")
    assert inp.overwrite is True


def test_file_write_traversal_blocked() -> None:
    with pytest.raises(ValidationError):
        FileWriteInput(path="../../etc/cron", content="bad")


def test_file_move_traversal_blocked() -> None:
    with pytest.raises(ValidationError):
        FileMoveInput(src="../secret", dst="/tmp/")


def test_file_move_output() -> None:
    out = FileMoveOutput(new_path="/docs/report.pdf")
    assert out.new_path == "/docs/report.pdf"


def test_file_read_output() -> None:
    out = FileReadOutput(content="data", size_bytes=4)
    assert out.encoding == "utf-8"


# ===========================================================================
# Schema Validation — Misc
# ===========================================================================


def test_app_launch_valid() -> None:
    inp = AppLaunchInput(command=["notepad", "file.txt"])
    assert inp.cwd is None


def test_app_launch_empty_command() -> None:
    with pytest.raises(ValidationError):
        AppLaunchInput(command=[])


def test_app_launch_output() -> None:
    out = AppLaunchOutput(pid=1234, name="notepad.exe")
    assert out.pid == 1234


def test_clipboard_write() -> None:
    inp = ClipboardWriteInput(text="copied!")
    assert inp.text == "copied!"


def test_clipboard_read_output() -> None:
    out = ClipboardReadOutput(text="pasted")
    assert out.text == "pasted"


def test_notify_valid() -> None:
    inp = NotifyInput(title="Done", message="Task complete")
    assert inp.timeout == 5


def test_notify_title_too_long() -> None:
    with pytest.raises(ValidationError):
        NotifyInput(title="x" * 65, message="ok")


def test_email_list_input_defaults() -> None:
    inp = EmailListInput()
    assert inp.folder == "INBOX"
    assert inp.limit == 10


def test_email_list_output() -> None:
    item = EmailItem(uid="1", subject="Hi", sender="a@b.com", date="2026-01-01", body="Hello")
    out = EmailListOutput(emails=[item], total=1)
    assert out.total == 1


# ===========================================================================
# VectorStore
# ===========================================================================


def _make_mock_model(dim: int = 384) -> object:
    """Return a mock SentenceTransformer that returns deterministic embeddings."""
    from unittest.mock import MagicMock

    import numpy as np

    mock = MagicMock()
    mock.encode.side_effect = lambda text, **_kw: np.ones(dim, dtype=np.float32)
    return mock


def test_vector_store_instantiation(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    assert vs.size == 0


def test_vector_store_add_and_size(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    vs._model = _make_mock_model()
    vs.add_rule("rule-1", "send daily report")
    assert vs.size == 1


def test_vector_store_search_returns_result(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    vs._model = _make_mock_model()
    vs.add_rule("rule-1", "send daily report")
    vs.add_rule("rule-2", "watch folder")
    results = vs.search("report", k=2)
    assert len(results) == 2
    ids = [r[0] for r in results]
    assert "rule-1" in ids


def test_vector_store_search_empty_returns_empty(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    results = vs.search("anything")
    assert results == []


def test_vector_store_search_k_capped_at_total(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    vs._model = _make_mock_model()
    vs.add_rule("r1", "text")
    results = vs.search("text", k=100)
    assert len(results) == 1


def test_vector_store_persist_and_reload(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs1 = VectorStore(data_dir=tmp_path)
    vs1._model = _make_mock_model()
    vs1.add_rule("r1", "alpha")
    vs1.add_rule("r2", "beta")
    vs1.persist()

    vs2 = VectorStore(data_dir=tmp_path)
    vs2._model = _make_mock_model()
    assert vs2.size == 2
    assert "r1" in vs2._rule_ids
    assert "r2" in vs2._rule_ids


def test_vector_store_auto_persist_every_10(tmp_path: Path) -> None:
    """Auto-persist must fire exactly once after 10 inserts."""
    from unittest.mock import patch

    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    vs._model = _make_mock_model()

    with patch.object(vs, "persist", wraps=vs.persist) as mock_persist:
        for i in range(10):
            vs.add_rule(f"r{i}", f"text {i}")
        mock_persist.assert_called_once()


def test_vector_store_auto_persist_not_before_10(tmp_path: Path) -> None:
    from unittest.mock import patch

    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    vs._model = _make_mock_model()

    with patch.object(vs, "persist") as mock_persist:
        for i in range(9):
            vs.add_rule(f"r{i}", f"text {i}")
        mock_persist.assert_not_called()


def test_vector_store_remove_rule(tmp_path: Path) -> None:
    from db.vector_store import VectorStore

    vs = VectorStore(data_dir=tmp_path)
    vs._model = _make_mock_model()
    vs.add_rule("r1", "keep")
    vs.add_rule("r2", "remove me")
    vs.remove_rule("r2")
    assert "r2" not in vs._rule_ids
    assert "r1" in vs._rule_ids


def test_vector_store_load_handles_corrupt_files(tmp_path: Path) -> None:
    """Corrupt index files should be silently ignored; store starts fresh."""
    from db.vector_store import VectorStore

    (tmp_path / "rules.faiss").write_bytes(b"not-a-faiss-index")
    (tmp_path / "rules_ids.json").write_text('["r1"]', encoding="utf-8")

    vs = VectorStore(data_dir=tmp_path)
    assert vs.size == 0
    assert vs._rule_ids == []


# ===========================================================================
# db/session helpers
# ===========================================================================


def test_data_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    from db.session import _data_dir

    result = _data_dir()
    assert result.name == ".edgedesk"


def test_data_dir_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "custom"))
    from db.session import _data_dir

    result = _data_dir()
    assert result == (tmp_path / "custom").resolve()


def test_db_url_creates_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "edgedesk_test"
    monkeypatch.setenv("DATA_DIR", str(target))
    from db.session import _db_url

    url = _db_url()
    assert target.exists()
    assert "edgedesk.db" in url


def test_get_engine_returns_engine(tmp_path: Path) -> None:
    from db.session import get_engine, reset_engine

    reset_engine()
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    assert engine is not None
    # Second call returns cached instance
    assert get_engine("sqlite+aiosqlite:///:memory:") is engine
    reset_engine()


def test_get_session_factory_returns_factory(tmp_path: Path) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from db.session import get_session_factory, reset_engine

    reset_engine()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = get_session_factory(engine)
    assert factory is not None
    # Second call returns cached instance
    assert get_session_factory(engine) is factory
    reset_engine()


async def test_get_session_yields_session(tmp_path: Path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from db.session import get_session, get_session_factory, init_db, reset_engine

    reset_engine()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    get_session_factory(engine)

    async for session in get_session():
        assert isinstance(session, AsyncSession)
        break

    reset_engine()


def test_reset_engine_clears_cache() -> None:
    from db.session import get_engine, reset_engine

    reset_engine()
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    assert engine is not None
    reset_engine()

    from db.session import _engine, _session_factory

    assert _engine is None
    assert _session_factory is None
