"""EdgeDesk agent orchestrator.

Wraps a langgraph ReAct graph and exposes a single `run()` async generator
that streams tokens to the caller.  The orchestrator is stateful per session
(via MemorySaver checkpointing) and persists a summary to SQLite separately.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from langchain.agents import create_agent as create_react_agent  # type: ignore[attr-defined]
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from core.prompts import build_system_prompt
from schemas.models import ToolError


class AgentOrchestrator:
    """Runs a langgraph ReAct agent and streams response tokens.

    The agent graph is built once on construction and reused for all
    `run()` calls within the same session (memory is preserved via
    the MemorySaver checkpointer keyed to `session_id`).

    Args:
        llm: A LangChain-compatible chat model (ChatOllama in production,
             a mock in tests).
        tools: List of LangChain `BaseTool` instances from `tools/__init__.py`.
        session_id: Unique key used for checkpointing and memory isolation.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        session_id: str = "default",
    ) -> None:
        self._llm = llm
        self._session_id = session_id
        self._checkpointer = MemorySaver()
        system_msg = SystemMessage(content=build_system_prompt([t.name for t in tools]))
        self._graph = create_react_agent(
            llm,
            tools=tools,
            system_prompt=system_msg,
            checkpointer=self._checkpointer,
        )
        logger.info(
            "AgentOrchestrator ready — session='{}', tools={}",
            session_id,
            [t.name for t in tools],
        )

    async def run(self, instruction: str) -> AsyncIterator[str]:
        """Execute *instruction* and stream response tokens.

        Yields string tokens as they arrive from the LLM.  On error, yields
        a JSON-serialised `ToolError` as the final (and only) token.
        """
        config: RunnableConfig = {"configurable": {"thread_id": self._session_id}}
        logger.info("Agent run — session='{}': {!r}", self._session_id, instruction[:80])
        try:
            yielded_any = False
            async for event in self._graph.astream_events(
                {"messages": [("human", instruction)]},
                version="v2",
                config=config,
            ):
                kind: str = event["event"]
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yielded_any = True
                        yield content

            # Fallback for non-streaming models: read final state
            if not yielded_any:
                state = await self._graph.aget_state(config)
                messages = state.values.get("messages", [])
                for msg in reversed(messages):
                    if (
                        hasattr(msg, "content")
                        and msg.content
                        and not getattr(msg, "tool_calls", None)
                    ):
                        yield msg.content
                        break

        except OutputParserException as exc:
            logger.error("OutputParserException: {}", exc)
            yield ToolError(tool="agent", message=str(exc), retryable=True).model_dump_json()
        except Exception as exc:
            logger.error("Agent error: {}", exc)
            yield ToolError(tool="agent", message=str(exc), retryable=False).model_dump_json()

    @property
    def session_id(self) -> str:
        """The session identifier for this orchestrator instance."""
        return self._session_id
