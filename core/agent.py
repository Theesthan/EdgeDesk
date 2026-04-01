"""EdgeDesk agent orchestrator.

Wraps a langgraph ReAct graph and exposes a single `run()` async generator
that streams tokens to the caller.

The orchestrator supports per-call thread IDs so callers can isolate context
between individual steps (main._run_instruction uses this to keep each step's
context window small and prevent small models from stopping early).
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

    Args:
        llm: A LangChain-compatible chat model.
        tools: List of LangChain BaseTool instances from tools/__init__.py.
        session_id: Default thread ID for checkpointing. Can be overridden
            per call via the thread_id param of run().
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        session_id: str = "default",
    ) -> None:
        self._llm = llm
        self._tools = tools
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

    async def run(
        self,
        instruction: str,
        thread_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Execute *instruction* and stream response tokens.

        Args:
            instruction: The prompt / instruction to run.
            thread_id: Optional thread ID override. Pass a unique value per
                step to give each step a fresh conversation context with a
                small context window. Defaults to self._session_id.

        Yields:
            String tokens as they arrive from the LLM. On error yields a
            JSON-serialised ToolError as the final token.
        """
        tid = thread_id if thread_id is not None else self._session_id
        config: RunnableConfig = {"configurable": {"thread_id": tid}}
        logger.info("Agent run — thread='{}': {!r}", tid, instruction[:80])
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

            # Fallback for non-streaming models
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
        """The default session identifier for this orchestrator instance."""
        return self._session_id
