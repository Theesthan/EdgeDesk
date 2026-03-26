"""Root-level pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    """Use the default event loop policy for all async tests."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def tmp_data_dir(tmp_path: pytest.TempPathFactory) -> Generator[str, None, None]:
    """Override DATA_DIR to a temporary path so tests never touch ~/.edgedesk."""
    import os

    original = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(tmp_path)
    yield str(tmp_path)
    if original is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = original
