"""Tests for the EdgeDesk UI design system.

Theme constants and QSS functions are tested without a display.
Component import tests run only when PyQt6 is available.
"""

from __future__ import annotations

import pytest


# ===========================================================================
# ui/styles/theme.py — design tokens
# ===========================================================================


def test_color_tokens_are_hex_or_rgba() -> None:
    from ui.styles.theme import (
        ACCENT_ERROR,
        ACCENT_GLOW,
        ACCENT_PRIMARY,
        ACCENT_SUCCESS,
        ACCENT_WARNING,
        BG_ELEVATED,
        BG_PRIMARY,
        BG_SURFACE,
        GLASS_BG,
        GLASS_BORDER,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        TEXT_TERTIARY,
    )
    hex_tokens = [BG_PRIMARY, BG_SURFACE, BG_ELEVATED, ACCENT_PRIMARY, ACCENT_SUCCESS,
                  ACCENT_WARNING, ACCENT_ERROR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY]
    rgba_tokens = [GLASS_BG, GLASS_BORDER, ACCENT_GLOW]

    for token in hex_tokens:
        assert token.startswith("#"), f"{token!r} should be a hex color"
        assert len(token) in (7, 9), f"{token!r} should be #rrggbb or #rrggbbaa"

    for token in rgba_tokens:
        assert token.startswith("rgba("), f"{token!r} should be rgba(...)"


def test_bg_primary_exact_value() -> None:
    from ui.styles.theme import BG_PRIMARY
    assert BG_PRIMARY == "#0a0a0f"


def test_accent_primary_exact_value() -> None:
    from ui.styles.theme import ACCENT_PRIMARY
    assert ACCENT_PRIMARY == "#7c6af7"


def test_radius_tokens_are_ints_and_ascending() -> None:
    from ui.styles.theme import RADIUS_LG, RADIUS_MD, RADIUS_SM, RADIUS_XL
    assert isinstance(RADIUS_SM, int)
    assert RADIUS_SM < RADIUS_MD < RADIUS_LG < RADIUS_XL


def test_radius_exact_values() -> None:
    from ui.styles.theme import RADIUS_LG, RADIUS_MD, RADIUS_SM, RADIUS_XL
    assert RADIUS_SM == 6
    assert RADIUS_MD == 10
    assert RADIUS_LG == 16
    assert RADIUS_XL == 22


def test_spacing_grid_are_multiples_of_4() -> None:
    from ui.styles.theme import SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8
    for space in (SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8):
        assert space % 4 == 0, f"SPACE={space} is not a multiple of 4"


def test_spacing_exact_values() -> None:
    from ui.styles.theme import SPACE_1, SPACE_2, SPACE_4
    assert SPACE_1 == 4
    assert SPACE_2 == 8
    assert SPACE_4 == 16


def test_font_sizes_are_positive_ints() -> None:
    from ui.styles.theme import (
        FONT_SIZE_BODY,
        FONT_SIZE_CAPTION,
        FONT_SIZE_CODE,
        FONT_SIZE_TITLE,
    )
    for size in (FONT_SIZE_TITLE, FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_CODE):
        assert isinstance(size, int) and size > 0


def test_fonts_dir_path_has_correct_structure() -> None:
    from pathlib import Path

    from ui.styles.theme import FONTS_DIR
    assert isinstance(FONTS_DIR, Path)
    assert FONTS_DIR.name == "fonts"
    assert FONTS_DIR.parent.name == "assets"


# ===========================================================================
# ui/styles/qss.py — QSS template functions
# ===========================================================================


def test_glass_card_qss_contains_required_keys() -> None:
    from ui.styles.qss import glass_card_qss
    qss = glass_card_qss()
    assert "GlassCard" in qss
    assert "border-radius" in qss
    assert "rgba" in qss      # GLASS_BG / GLASS_BORDER use rgba


def test_glass_card_qss_accepts_custom_radius() -> None:
    from ui.styles.qss import glass_card_qss
    qss = glass_card_qss(radius=22)
    assert "22px" in qss


def test_input_field_qss_covers_focus_state() -> None:
    from ui.styles.qss import input_field_qss
    qss = input_field_qss()
    assert "QLineEdit" in qss
    assert "focus" in qss
    assert "border-bottom" in qss


def test_scrollbar_qss_covers_both_orientations() -> None:
    from ui.styles.qss import scrollbar_qss
    qss = scrollbar_qss()
    assert "QScrollBar:vertical" in qss
    assert "QScrollBar:horizontal" in qss
    assert "QScrollBar::handle" in qss


def test_button_qss_primary_uses_accent_color() -> None:
    from ui.styles.qss import button_qss
    from ui.styles.theme import ACCENT_PRIMARY
    qss = button_qss("primary")
    assert ACCENT_PRIMARY in qss
    assert "QPushButton" in qss


def test_button_qss_ghost_uses_transparent_bg() -> None:
    from ui.styles.qss import button_qss
    qss = button_qss("ghost")
    assert "transparent" in qss
    assert "border:" in qss


def test_button_qss_default_is_primary() -> None:
    from ui.styles.qss import button_qss
    assert button_qss() == button_qss("primary")


def test_tab_button_qss_active_uses_primary_text() -> None:
    from ui.styles.qss import tab_button_qss
    from ui.styles.theme import TEXT_PRIMARY, TEXT_SECONDARY
    active_qss = tab_button_qss(active=True)
    inactive_qss = tab_button_qss(active=False)
    assert TEXT_PRIMARY in active_qss
    assert TEXT_SECONDARY in inactive_qss


# ===========================================================================
# ui/styles/components.py — import smoke tests (requires PyQt6)
# ===========================================================================


def test_component_classes_are_importable() -> None:
    """Importing all 6 widget classes must not raise."""
    try:
        from ui.styles.components import (  # noqa: F401
            AccentButton,
            AnimatedTabBar,
            GlassCard,
            StepPill,
            StatusDot,
            ToggleSwitch,
        )
    except ImportError as exc:
        pytest.skip(f"PyQt6 not available: {exc}")


def test_status_meta_covers_all_states() -> None:
    """_STATUS_META must define all four step states."""
    try:
        from ui.styles.components import _STATUS_META
    except ImportError:
        pytest.skip("PyQt6 not available")
    for state in ("pending", "running", "done", "failed"):
        assert state in _STATUS_META, f"Missing status: {state!r}"
        color, icon = _STATUS_META[state]
        assert color.startswith("#") or color.startswith("rgba"), (
            f"status {state!r} color {color!r} is not a valid color token"
        )
