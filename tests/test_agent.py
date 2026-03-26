"""Tests for core agent components: LLM, memory, orchestrator, planner."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent import AgentOrchestrator
from core.llm import (
    MODEL_HIGH_VRAM,
    MODEL_LOW_VRAM,
    VRAM_HIGH_THRESHOLD_MB,
    detect_vram_mb,
    health_check,
    select_model,
)
from core.memory import AgentMemory
from core.planner import TaskPlanner
from core.prompts import build_system_prompt

# ===========================================================================
# Mock LLM helpers
# ===========================================================================


class MockChatModel(BaseChatModel):
    """Synchronous mock — returns a fixed response, no streaming."""

    response: str = "Task completed."

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.response))]
        )


class MockStreamingChatModel(BaseChatModel):
    """Streaming mock — yields one token per word via _astream."""

    response: str = "Hello from EdgeDesk."

    @property
    def _llm_type(self) -> str:
        return "mock-streaming"

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.response))]
        )

    def _stream(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        for word in self.response.split():
            token = word + " "
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=token))
            if run_manager:
                run_manager.on_llm_new_token(token, chunk=chunk)
            yield chunk

    async def _astream(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        for word in self.response.split():
            token = word + " "
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=token))
            if run_manager:
                await run_manager.on_llm_new_token(token, chunk=chunk)
            yield chunk


# ===========================================================================
# core/llm.py — model selection
# ===========================================================================


def test_select_model_high_vram() -> None:
    assert select_model(vram_mb=VRAM_HIGH_THRESHOLD_MB) == MODEL_HIGH_VRAM


def test_select_model_high_vram_above_threshold() -> None:
    assert select_model(vram_mb=16384) == MODEL_HIGH_VRAM


def test_select_model_low_vram() -> None:
    assert select_model(vram_mb=4096) == MODEL_LOW_VRAM


def test_select_model_zero_vram() -> None:
    assert select_model(vram_mb=0) == MODEL_LOW_VRAM


def test_select_model_explicit_override() -> None:
    assert select_model(override="gemma:7b") == "gemma:7b"


def test_select_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "phi4:14b")
    # Clear any override to let env take priority
    assert select_model(vram_mb=0) == "phi4:14b"


def test_select_model_override_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "phi4:14b")
    assert select_model(override="custom:model") == "custom:model"


def test_detect_vram_returns_int() -> None:
    result = detect_vram_mb()
    assert isinstance(result, int)
    assert result >= 0


# ===========================================================================
# core/llm.py — health check
# ===========================================================================


async def test_health_check_success() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("core.llm.httpx.AsyncClient", return_value=mock_client):
        await health_check("http://localhost:11434")  # should not raise

    mock_client.get.assert_called_once_with("http://localhost:11434/api/tags")


async def test_health_check_connection_refused() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("core.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ConnectionError, match="Ollama is not reachable"):
            await health_check("http://localhost:11434")


async def test_health_check_http_error() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("core.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ConnectionError):
            await health_check("http://localhost:11434")


# ===========================================================================
# core/prompts.py
# ===========================================================================


def test_build_system_prompt_contains_tools() -> None:
    prompt = build_system_prompt(["screen_capture", "gui_click"])
    assert "screen_capture" in prompt
    assert "gui_click" in prompt


def test_build_system_prompt_no_tools() -> None:
    prompt = build_system_prompt([])
    assert "none" in prompt


def test_build_system_prompt_has_privacy_reminder() -> None:
    prompt = build_system_prompt(["any_tool"])
    assert "internet" in prompt.lower() or "external" in prompt.lower()


def test_build_system_prompt_has_datetime() -> None:
    prompt = build_system_prompt([])
    assert "UTC" in prompt


# ===========================================================================
# core/memory.py
# ===========================================================================


async def test_memory_save_and_load(db_session: AsyncSession) -> None:
    memory = AgentMemory("sess-1", db_session)
    await memory.save("The user prefers concise answers.")
    assert memory.get_summary() == "The user prefers concise answers."

    # A fresh instance for the same session should load from DB
    memory2 = AgentMemory("sess-1", db_session)
    loaded = await memory2.load()
    assert loaded == "The user prefers concise answers."


async def test_memory_upsert(db_session: AsyncSession) -> None:
    memory = AgentMemory("sess-2", db_session)
    await memory.save("Version 1")
    await memory.save("Version 2")

    memory2 = AgentMemory("sess-2", db_session)
    loaded = await memory2.load()
    assert loaded == "Version 2"


async def test_memory_load_missing_session(db_session: AsyncSession) -> None:
    memory = AgentMemory("nonexistent-session", db_session)
    result = await memory.load()
    assert result == ""


async def test_memory_clear(db_session: AsyncSession) -> None:
    memory = AgentMemory("sess-3", db_session)
    await memory.save("Some context")
    memory.clear()
    assert memory.get_summary() == ""
    # DB still has the value
    memory2 = AgentMemory("sess-3", db_session)
    assert await memory2.load() == "Some context"


# ===========================================================================
# core/agent.py — streaming
# ===========================================================================


async def test_agent_run_streams_tokens() -> None:
    """Tokens from the mock streaming LLM must be yielded one-by-one."""
    mock_llm = MockStreamingChatModel(response="Hello from EdgeDesk.")
    orchestrator = AgentOrchestrator(mock_llm, tools=[], session_id="stream-test")

    collected: list[str] = []
    async for token in orchestrator.run("say hello"):
        collected.append(token)

    full_text = "".join(collected).strip()
    assert "Hello" in full_text
    assert len(collected) >= 1


async def test_agent_run_fallback_nonstreaming() -> None:
    """Non-streaming mock must still yield the final response."""
    mock_llm = MockChatModel(response="Done with the task.")
    orchestrator = AgentOrchestrator(mock_llm, tools=[], session_id="fallback-test")

    collected: list[str] = []
    async for token in orchestrator.run("do something"):
        collected.append(token)

    assert len(collected) >= 1
    assert "Done" in "".join(collected)


async def test_agent_session_id() -> None:
    mock_llm = MockChatModel()
    orchestrator = AgentOrchestrator(mock_llm, tools=[], session_id="my-session")
    assert orchestrator.session_id == "my-session"


# ===========================================================================
# core/planner.py
# ===========================================================================


async def test_planner_parses_numbered_list() -> None:
    mock_llm = MockChatModel(
        response="1. Open Notepad\n2. Type the text\n3. Save the file"
    )
    planner = TaskPlanner(mock_llm)
    steps = await planner.decompose("Write and save a note")
    assert len(steps) == 3
    assert steps[0] == "Open Notepad"
    assert steps[1] == "Type the text"
    assert steps[2] == "Save the file"


async def test_planner_parses_paren_style() -> None:
    mock_llm = MockChatModel(response="1) Launch app\n2) Click button\n3) Done")
    planner = TaskPlanner(mock_llm)
    steps = await planner.decompose("Click something")
    assert len(steps) == 3
    assert steps[0] == "Launch app"


async def test_planner_fallback_on_unparseable(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_llm = MockChatModel(response="I cannot determine the steps for this task.")
    planner = TaskPlanner(mock_llm)
    steps = await planner.decompose("Do something")
    # Falls back to single-step list with the original instruction
    assert steps == ["Do something"]


async def test_planner_strips_empty_lines() -> None:
    mock_llm = MockChatModel(response="\n1. Step one\n\n2. Step two\n")
    planner = TaskPlanner(mock_llm)
    steps = await planner.decompose("Multi-step task")
    assert len(steps) == 2
