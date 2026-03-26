"""Task decomposition planner.

Takes a high-level natural language instruction and uses the LLM to break it
into an ordered list of concrete sub-steps, which are then fed one-by-one to
the agent executor.
"""

from __future__ import annotations

import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from loguru import logger

_DECOMPOSE_PROMPT = """\
You are a task planner. Break the following task into 3-7 ordered, concrete steps.

Task: {instruction}

Rules:
- Each step must be a single, atomic action (open an app, click a button, type text, etc.)
- Use a numbered list: "1. ...", "2. ...", etc.
- No explanations — just the numbered list.
"""

_STEP_PATTERN: re.Pattern[str] = re.compile(r"^\s*\d+[\.\)]\s*(.+)$")


class TaskPlanner:
    """Decomposes a natural-language instruction into ordered sub-steps.

    Args:
        llm: A LangChain-compatible chat model.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def decompose(self, instruction: str) -> list[str]:
        """Return an ordered list of sub-steps for *instruction*.

        Falls back to `[instruction]` (single step) if the LLM output
        cannot be parsed as a numbered list.
        """
        prompt = _DECOMPOSE_PROMPT.format(instruction=instruction)
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        steps = self._parse_steps(str(response.content))
        if not steps:
            logger.warning("Planner returned no parseable steps; falling back to single step.")
            return [instruction]
        logger.debug("Planner decomposed '{}' into {} steps.", instruction[:60], len(steps))
        return steps

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_steps(text: str) -> list[str]:
        """Extract numbered list items from raw LLM output."""
        steps: list[str] = []
        for line in text.strip().splitlines():
            match = _STEP_PATTERN.match(line)
            if match:
                step = match.group(1).strip()
                if step:
                    steps.append(step)
        return steps
