"""EdgeDesk system tray application.

Provides the persistent system tray icon and context menu that gives access to
all application panels. All panel-open actions emit signals so main.py can
connect them to the appropriate panel instances.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

try:
    import qtawesome as qta  # type: ignore[import]

    _QTA = True
except ImportError:
    _QTA = False

from ui.styles.theme import (
    ACCENT_PRIMARY,
    BG_ELEVATED,
    FONT_SIZE_BODY,
    GLASS_BG,
    GLASS_BORDER,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_4,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MENU_QSS: str = f"""
    QMenu {{
        background: {BG_ELEVATED};
        border: 1px solid {GLASS_BORDER};
        border-radius: {RADIUS_MD}px;
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_BODY}px;
        padding: {SPACE_1}px;
    }}
    QMenu::item {{
        padding: {SPACE_2}px {SPACE_4}px;
        border-radius: {RADIUS_SM}px;
    }}
    QMenu::item:selected {{
        background: {GLASS_BG};
        color: {TEXT_PRIMARY};
    }}
    QMenu::separator {{
        height: 1px;
        background: {GLASS_BORDER};
        margin: {SPACE_1}px {SPACE_2}px;
    }}
"""


def _make_tray_icon() -> QIcon:
    """Return an AccentPrimary-coloured robot icon, or a painted fallback."""
    if _QTA:
        return qta.icon("fa5s.robot", color=ACCENT_PRIMARY)
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(ACCENT_PRIMARY))
    p.setPen(QColor(0, 0, 0, 0))
    p.drawEllipse(4, 4, 24, 24)
    p.end()
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# SystemTrayApp
# ---------------------------------------------------------------------------


class SystemTrayApp(QSystemTrayIcon):
    """Persistent tray icon. All actions emit signals; main.py wires them up.

    Signals:
        open_overlay_requested: User chose "Open Overlay" or single-clicked the icon.
        open_rules_requested:   User chose "Rules".
        open_history_requested: User chose "History".
        open_settings_requested: User chose "Settings".
        quit_requested:         User chose "Quit".
    """

    open_overlay_requested: pyqtSignal = pyqtSignal()
    open_rules_requested: pyqtSignal = pyqtSignal()
    open_history_requested: pyqtSignal = pyqtSignal()
    open_settings_requested: pyqtSignal = pyqtSignal()
    quit_requested: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_make_tray_icon(), parent)
        self.setToolTip("EdgeDesk")
        self._build_menu()
        self.activated.connect(self._on_activated)

    # -- Public API ----------------------------------------------------------

    def show_notification(
        self, title: str, message: str, duration_ms: int = 5000
    ) -> None:
        """Show a standard system balloon notification."""
        self.showMessage(
            title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms
        )

    # -- Private -------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.setStyleSheet(_MENU_QSS)

        _entries: list[tuple[str, str, pyqtSignal]] = [
            ("fa5s.terminal", "Open Overlay   Alt+Space", self.open_overlay_requested),
            ("fa5s.list",     "Rules",                    self.open_rules_requested),
            ("fa5s.history",  "History",                  self.open_history_requested),
            ("fa5s.cog",      "Settings",                 self.open_settings_requested),
        ]

        icon_color = TEXT_SECONDARY
        for icon_name, label, signal in _entries:
            icon = qta.icon(icon_name, color=icon_color) if _QTA else QIcon()
            action = menu.addAction(icon, label)
            action.triggered.connect(signal.emit)

        menu.addSeparator()
        quit_icon = qta.icon("fa5s.times", color=icon_color) if _QTA else QIcon()
        quit_action = menu.addAction(quit_icon, "Quit")
        quit_action.triggered.connect(self.quit_requested.emit)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_overlay_requested.emit()
