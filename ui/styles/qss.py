"""QSS stylesheet template functions.

Each function returns a complete QSS string using design-token constants.
Call these in widget constructors — never write raw color strings in QSS.
"""

from __future__ import annotations

from ui.styles.theme import (
    ACCENT_GLOW,
    ACCENT_PRIMARY,
    BG_SURFACE,
    FONT_SIZE_BODY,
    GLASS_BG,
    GLASS_BORDER,
    RADIUS_MD,
    SPACE_2,
    SPACE_4,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)


def glass_card_qss(radius: int = RADIUS_MD) -> str:
    """QSS for a frosted-glass card container."""
    return f"""
        QFrame#GlassCard {{
            background-color: {GLASS_BG};
            border: 1px solid {GLASS_BORDER};
            border-radius: {radius}px;
        }}
    """


def input_field_qss() -> str:
    """QSS for the command-input QLineEdit."""
    return f"""
        QLineEdit {{
            background: transparent;
            border: none;
            border-bottom: 2px solid {GLASS_BORDER};
            border-radius: 0px;
            color: {TEXT_PRIMARY};
            font-size: {FONT_SIZE_BODY}px;
            padding: {SPACE_2}px {SPACE_4}px;
        }}
        QLineEdit:focus {{
            border-bottom: 2px solid {ACCENT_PRIMARY};
        }}
        QLineEdit[placeholderText] {{
            color: {TEXT_TERTIARY};
        }}
    """


def scrollbar_qss() -> str:
    """QSS for slim dark scrollbars (vertical + horizontal)."""
    return f"""
        QScrollBar:vertical {{
            background: {BG_SURFACE};
            width: 6px;
            border-radius: 3px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {GLASS_BORDER};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {TEXT_TERTIARY};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {BG_SURFACE};
            height: 6px;
            border-radius: 3px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {GLASS_BORDER};
            border-radius: 3px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {TEXT_TERTIARY};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
    """


def button_qss(variant: str = "primary") -> str:
    """QSS for AccentButton — 'primary' (filled) or 'ghost' (outlined)."""
    if variant == "ghost":
        return f"""
            QPushButton {{
                color: {ACCENT_PRIMARY};
                background: transparent;
                border: 1px solid {ACCENT_PRIMARY};
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_2}px {SPACE_4}px;
                font-size: {FONT_SIZE_BODY}px;
            }}
            QPushButton:hover {{
                background: {ACCENT_GLOW};
            }}
            QPushButton:pressed {{
                background: rgba(124,106,247,0.2);
            }}
        """
    # default: primary
    return f"""
        QPushButton {{
            color: {TEXT_PRIMARY};
            background: {ACCENT_PRIMARY};
            border: none;
            border-radius: {RADIUS_MD}px;
            padding: {SPACE_2}px {SPACE_4}px;
            font-size: {FONT_SIZE_BODY}px;
        }}
        QPushButton:hover {{
            background: #8d7ef8;
        }}
        QPushButton:pressed {{
            background: #6b58e0;
        }}
        QPushButton:disabled {{
            background: {TEXT_TERTIARY};
            color: {TEXT_SECONDARY};
        }}
    """


def tab_button_qss(active: bool = False) -> str:
    """QSS for individual tab buttons inside AnimatedTabBar."""
    color = TEXT_PRIMARY if active else TEXT_SECONDARY
    return (
        f"QPushButton {{ color: {color}; border: none; "
        f"padding: {SPACE_2}px {SPACE_4}px; "
        f"font-size: {FONT_SIZE_BODY}px; background: transparent; }} "
        f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
    )
