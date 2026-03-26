"""EdgeDesk — Local AI agent for privacy-first desktop automation.

Entry point: initialises the Qt application and system tray.
Full boot sequence implemented in Phase 9.
"""

from __future__ import annotations

from dotenv import load_dotenv
from loguru import logger


def main() -> None:
    """Boot EdgeDesk."""
    load_dotenv()
    logger.info("EdgeDesk starting…")
    # Phase 9 will wire: DB → VectorStore → LLM → Agent → Scheduler → UI
    logger.info("Boot sequence not yet implemented (Phase 9)")


if __name__ == "__main__":
    main()
