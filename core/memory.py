"""Persistent conversation memory for the EdgeDesk agent.

Stores a rolling summary to SQLite via `AgentMemoryRecord` so the agent
retains context across application restarts.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud import get_memory, upsert_memory


class AgentMemory:
    """Manages a per-session conversation summary persisted to SQLite.

    Usage::

        memory = AgentMemory(session_id="default", db_session=session)
        await memory.load()               # restore from DB
        await memory.save("Summary text") # persist new summary
        memory.get_summary()              # read in-memory value
        memory.clear()                    # reset (does not delete from DB)
    """

    def __init__(self, session_id: str, db_session: AsyncSession) -> None:
        self._session_id = session_id
        self._db_session = db_session
        self._summary: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def save(self, summary: str) -> None:
        """Persist *summary* to the database and cache it in memory."""
        self._summary = summary
        await upsert_memory(self._db_session, self._session_id, summary)
        await self._db_session.commit()
        logger.debug("AgentMemory saved for session '{}'.", self._session_id)

    async def load(self) -> str:
        """Load the stored summary from the database. Returns empty string if none."""
        record = await get_memory(self._db_session, self._session_id)
        if record is not None:
            self._summary = record.summary
            logger.debug(
                "AgentMemory loaded for session '{}': {} chars.",
                self._session_id,
                len(self._summary),
            )
        return self._summary

    def get_summary(self) -> str:
        """Return the in-memory summary (call `load()` first on a new instance)."""
        return self._summary

    def clear(self) -> None:
        """Reset the in-memory summary (does not delete from DB)."""
        self._summary = ""
        logger.debug("AgentMemory cleared for session '{}'.", self._session_id)

    @property
    def session_id(self) -> str:
        """The session identifier this memory belongs to."""
        return self._session_id
