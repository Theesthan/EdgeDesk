"""Screen capture and OCR tool.

Uses `mss` for fast screenshots and `pytesseract` for OCR.
Results are cached for 500 ms to avoid redundant captures within the same
agent step — cache key is the (region, time-bucket) tuple.
"""

from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any

import mss
import pytesseract
from langchain_core.tools import BaseTool
from loguru import logger
from PIL import Image

from schemas.models import ScreenCaptureInput, ScreenCaptureOutput, ToolError

# Configure Tesseract path from environment (Windows default)
_tess_cmd = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.isfile(_tess_cmd):
    pytesseract.pytesseract.tesseract_cmd = _tess_cmd

# Cache TTL bucket size in seconds (500 ms)
_CACHE_BUCKET_MS: int = 500


def _time_bucket() -> int:
    """Return current time rounded to the nearest 500 ms bucket."""
    return int(time.monotonic() * 1000) // _CACHE_BUCKET_MS


@lru_cache(maxsize=8)
def _cached_capture(
    region: tuple[int, int, int, int] | None,
    _bucket: int,
) -> str:
    """Capture screenshot and run OCR. Cached per region+time-bucket."""
    with mss.mss() as sct:
        if region:
            left, top, width, height = region
            monitor = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitor = sct.monitors[0]  # full virtual screen

        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    text: str = pytesseract.image_to_string(img)
    return text.strip()


class ScreenTool(BaseTool):
    """Capture the screen and extract text via OCR."""

    name: str = "screen_capture"
    description: str = "Capture screen region and extract visible text via OCR."
    args_schema: type = ScreenCaptureInput

    def _run(self, **kwargs: Any) -> ScreenCaptureOutput | ToolError:
        inp = ScreenCaptureInput(**kwargs)
        region = inp.region
        bucket = _time_bucket()
        logger.debug("screen_capture region={} bucket={}", region, bucket)
        try:
            text = _cached_capture(region, bucket)
            return ScreenCaptureOutput(text=text)
        except Exception as exc:
            logger.error("screen_capture failed: {}", exc)
            return ToolError(tool="screen_capture", message=str(exc), retryable=True)

    async def _arun(self, **kwargs: Any) -> ScreenCaptureOutput | ToolError:
        return self._run(**kwargs)
