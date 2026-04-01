"""Task decomposition planner.

Takes a high-level natural language instruction and uses the LLM to break it
into an ordered list of concrete sub-steps.
"""

from __future__ import annotations

import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from loguru import logger

from core.prompts import DECOMPOSE_PROMPT

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

        Falls back to ``[instruction]`` (single step) if the LLM output
        cannot be parsed as a numbered list.
        """
        prompt = DECOMPOSE_PROMPT.format(instruction=instruction)
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        steps = self._parse_steps(str(response.content))
        if not steps:
            logger.warning("Planner returned no parseable steps; falling back to single step.")
            return [instruction]
        logger.debug("Planner decomposed '{}' into {} steps.", instruction[:60], len(steps))
        return steps

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
