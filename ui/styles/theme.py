"""EdgeDesk design tokens.

All colors, radii, shadows, and spacing values live here.
Import these constants everywhere — never use magic numbers in UI code.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG_PRIMARY: str = "#0a0a0f"
BG_SURFACE: str = "#12121a"
BG_ELEVATED: str = "#1a1a26"
GLASS_BG: str = "rgba(255,255,255,0.04)"
GLASS_BORDER: str = "rgba(255,255,255,0.08)"

ACCENT_PRIMARY: str = "#7c6af7"
ACCENT_GLOW: str = "rgba(124,106,247,0.3)"
ACCENT_SUCCESS: str = "#22c55e"
ACCENT_WARNING: str = "#f59e0b"
ACCENT_ERROR: str = "#ef4444"

TEXT_PRIMARY: str = "#f0f0f8"
TEXT_SECONDARY: str = "#8888aa"
TEXT_TERTIARY: str = "#444466"

# ---------------------------------------------------------------------------
# Border radius (px)
# ---------------------------------------------------------------------------
RADIUS_SM: int = 6
RADIUS_MD: int = 10
RADIUS_LG: int = 16
RADIUS_XL: int = 22

# ---------------------------------------------------------------------------
# Shadows (CSS-style strings — used with QGraphicsDropShadowEffect)
# ---------------------------------------------------------------------------
SHADOW_CARD: str = "0 4px 24px rgba(0,0,0,0.5)"
SHADOW_GLOW: str = "0 0 20px rgba(124,106,247,0.25)"

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_PRIMARY: str = "Inter"
FONT_MONO: str = "JetBrains Mono"

FONT_SIZE_TITLE: int = 18
FONT_SIZE_BODY: int = 13
FONT_SIZE_CAPTION: int = 11
FONT_SIZE_CODE: int = 12

# ---------------------------------------------------------------------------
# Spacing grid — all values are multiples of 4 px
# ---------------------------------------------------------------------------
SPACE_1: int = 4
SPACE_2: int = 8
SPACE_3: int = 12
SPACE_4: int = 16
SPACE_6: int = 24
SPACE_8: int = 32

# ---------------------------------------------------------------------------
# Asset paths
# ---------------------------------------------------------------------------
_ASSETS_DIR: Path = Path(__file__).parent.parent / "assets"
FONTS_DIR: Path = _ASSETS_DIR / "fonts"


def apply_font(app: object) -> None:
    """Load bundled fonts and set the application default font.

    Loads all `.ttf` files from `ui/assets/fonts/` via `QFontDatabase`.
    Silently falls back to system fonts (Segoe UI) if font files are absent.

    Args:
        app: A `QApplication` instance.
    """
    try:
        from PyQt6.QtGui import QFont, QFontDatabase

        for font_file in FONTS_DIR.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_file))

        font = QFont(FONT_PRIMARY)
        font.setPixelSize(FONT_SIZE_BODY)
        app.setFont(font)  # type: ignore[attr-defined]
    except Exception:
        pass  # graceful: system fonts used if PyQt6 unavailable or fonts missing
