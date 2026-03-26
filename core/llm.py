"""Local LLM connection via Ollama.

Detects available VRAM and selects the best model automatically.
Provides an async health check so the app can warn users if Ollama
is not running, without hard-failing on startup.
"""

from __future__ import annotations

import os
import subprocess

import httpx
from langchain_ollama import ChatOllama
from loguru import logger

VRAM_HIGH_THRESHOLD_MB: int = 8192
MODEL_HIGH_VRAM: str = "mistral-nemo:12b"
MODEL_LOW_VRAM: str = "phi3.5:3.8b"
DEFAULT_BASE_URL: str = "http://localhost:11434"
DEFAULT_TEMPERATURE: float = 0.1
DEFAULT_NUM_CTX: int = 4096


def detect_vram_mb() -> int:
    """Query nvidia-smi for total VRAM in MB. Returns 0 on any error."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except Exception as exc:
        logger.debug("VRAM detection unavailable: {}", exc)
    return 0


def select_model(vram_mb: int | None = None, override: str | None = None) -> str:
    """Choose the best available Ollama model.

    Priority: explicit *override* > OLLAMA_MODEL env var > VRAM-based auto-select.
    """
    if override:
        return override
    env_model = os.environ.get("OLLAMA_MODEL")
    if env_model:
        return env_model
    vram = vram_mb if vram_mb is not None else detect_vram_mb()
    model = MODEL_HIGH_VRAM if vram >= VRAM_HIGH_THRESHOLD_MB else MODEL_LOW_VRAM
    logger.info("Auto-selected model: {} (VRAM: {} MB)", model, vram)
    return model


async def health_check(base_url: str = DEFAULT_BASE_URL) -> None:
    """Verify Ollama is running. Raises `ConnectionError` if unreachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
        logger.debug("Ollama health check OK at {}", base_url)
    except Exception as exc:
        raise ConnectionError(
            f"Ollama is not reachable at {base_url}. Start it with `ollama serve`. Error: {exc}"
        ) from exc


def build_llm(
    model: str | None = None,
    base_url: str | None = None,
) -> ChatOllama:
    """Construct and return a `ChatOllama` instance.

    Does NOT perform the health check — call `health_check()` separately.
    """
    resolved_model = model or select_model()
    resolved_url = base_url or os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
    logger.info("Building ChatOllama: model={}, base_url={}", resolved_model, resolved_url)
    return ChatOllama(
        model=resolved_model,
        base_url=resolved_url,
        temperature=DEFAULT_TEMPERATURE,
        num_ctx=DEFAULT_NUM_CTX,
    )
