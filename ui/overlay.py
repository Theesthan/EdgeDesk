"""EdgeDesk command overlay.

Frameless glass window triggered by Alt+Space. Shows an input field and a
scrollable log of step pills as the agent executes.

Run directly for a visual demo: uv run python ui/overlay.py
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import (  # type: ignore[attr-defined]
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QMouseEvent, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.styles.components import StepPill
from ui.styles.qss import scrollbar_qss
from ui.styles.theme import (
    ACCENT_PRIMARY,
    FONT_SIZE_BODY,
    GLASS_BG,
    GLASS_BORDER,
    RADIUS_XL,
    SPACE_4,
    TEXT_PRIMARY,
)

# ---------------------------------------------------------------------------
# DWM helper (Windows only)
# ---------------------------------------------------------------------------


def _apply_dwm_blur(window: QWidget) -> None:
    """Apply Windows DWM acrylic blur via DwmExtendFrameIntoClientArea.

    No-op on non-Windows platforms; failures are silently ignored.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        class _MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        margins = _MARGINS(-1, -1, -1, -1)
        hwnd = ctypes.c_int(int(window.winId()))
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(  # type: ignore[attr-defined]
            hwnd, ctypes.byref(margins)
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# InputBar
# ---------------------------------------------------------------------------


class InputBar(QLineEdit):
    """Command input field with an animated ACCENT_PRIMARY bottom border on focus."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setPlaceholderText("Ask EdgeDesk anything...")
        self.setStyleSheet(
            f"QLineEdit {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  color: {TEXT_PRIMARY};"
            f"  font-size: {FONT_SIZE_BODY}px;"
            f"  padding: 0 {SPACE_4}px;"
            f"  selection-background-color: {ACCENT_PRIMARY};"
            f"}}"
        )
        self.__focus_t: float = 0.0
        self._anim = QPropertyAnimation(self, b"focus_t", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def focus_t(self) -> float:  # type: ignore[override]
        return self.__focus_t

    @focus_t.setter  # type: ignore[override, no-redef]
    def focus_t(self, v: float) -> None:
        self.__focus_t = v
        self.update()

    def focusInEvent(self, event: object) -> None:  # type: ignore[override]
        super().focusInEvent(event)  # type: ignore[arg-type]
        self._anim.setStartValue(self.__focus_t)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def focusOutEvent(self, event: object) -> None:  # type: ignore[override]
        super().focusOutEvent(event)  # type: ignore[arg-type]
        self._anim.setStartValue(self.__focus_t)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        super().paintEvent(event)  # type: ignore[arg-type]
        p = QPainter(self)
        p.setPen(Qt.PenStyle.NoPen)
        t = self.__focus_t
        # Interpolate rgba(255,255,255,0.08) -> ACCENT_PRIMARY #7c6af7
        r = int(255 + (0x7C - 255) * t)
        g = int(255 + (0x6A - 255) * t)
        b = int(255 + (0xF7 - 255) * t)
        a = int(20 + (255 - 20) * t)  # 0.08 * 255 ~ 20
        p.setBrush(QBrush(QColor(r, g, b, a)))
        p.drawRect(0, self.height() - 2, self.width(), 2)
        p.end()


# ---------------------------------------------------------------------------
# StepLogArea
# ---------------------------------------------------------------------------


class StepLogArea(QScrollArea):
    """Scrollable container for StepPill widgets; height-animates open on first use."""

    _MAX_H: int = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMaximumHeight(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }" + scrollbar_qss()
        )

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(SPACE_4, 0, SPACE_4, SPACE_4)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self.setWidget(self._container)

        self._height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._height_anim.setDuration(150)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pills: dict[str, StepPill] = {}

    def add_step_pill(self, step_id: str, text: str = "", status: str = "pending") -> StepPill:
        """Insert a new StepPill before the trailing stretch and animate open if needed."""
        pill = StepPill(text=text, status=status, parent=self._container)
        insert_idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(insert_idx, pill)
        self._pills[step_id] = pill

        if self.maximumHeight() == 0:
            self._height_anim.stop()
            self._height_anim.setStartValue(0)
            self._height_anim.setEndValue(self._MAX_H)
            self._height_anim.start()

        if bar := self.verticalScrollBar():
            bar.setValue(bar.maximum())
        return pill

    def get_step_pill(self, step_id: str) -> StepPill | None:
        """Return the StepPill for *step_id*, or ``None`` if not found."""
        return self._pills.get(step_id)

    def clear_steps(self) -> None:
        """Remove all pills and collapse the area to zero height."""
        self._height_anim.stop()
        for pill in self._pills.values():
            pill.deleteLater()
        self._pills.clear()
        while self._layout.count() > 1:  # keep the trailing stretch
            item = self._layout.takeAt(0)
            if item:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        self.setMaximumHeight(0)


# ---------------------------------------------------------------------------
# OverlayWindow
# ---------------------------------------------------------------------------


class OverlayWindow(QWidget):
    """Frameless glass overlay — the EdgeDesk command palette.

    Signals:
        instruction_submitted(str): Emitted when the user presses Enter.

    Slots:
        on_token(str): Append a streamed LLM token to the current step pill.
        on_step_update(str, str, str): Create or update a step pill by ID.
    """

    instruction_submitted: pyqtSignal = pyqtSignal(str)

    _WIDTH: int = 680

    def __init__(
        self,
        orchestrator: object | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._orchestrator = orchestrator
        self._current_step_id: str | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(self._WIDTH)

        self._build_ui()
        self._build_animations()

        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    # -- Construction --------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QWidget(self)
        self._card.setObjectName("OverlayCard")
        self._card.setStyleSheet(
            f"QWidget#OverlayCard {{"
            f"  background: {GLASS_BG};"
            f"  border: 1px solid {GLASS_BORDER};"
            f"  border-radius: {RADIUS_XL}px;"
            f"}}"
        )
        outer.addWidget(self._card)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(0, 0, 0, SPACE_4)
        layout.setSpacing(0)

        self._input = InputBar(self._card)
        self._input.returnPressed.connect(self._on_return)
        layout.addWidget(self._input)

        self._steps = StepLogArea(self._card)
        layout.addWidget(self._steps)

    def _build_animations(self) -> None:
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._opacity_anim.setDuration(180)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(180)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -- Public API ----------------------------------------------------------

    def show_overlay(self) -> None:
        """Reset state, center on screen, and animate the overlay into view."""
        self._opacity_anim.stop()
        self._pos_anim.stop()
        try:
            self._opacity_anim.finished.disconnect(self._on_dismissed)
        except RuntimeError:
            pass

        self._input.clear()
        self._steps.clear_steps()
        self._current_step_id = None

        target = self._center_pos()
        start = QPoint(target.x(), target.y() + 20)

        self.setWindowOpacity(0.0)
        self.move(start)
        self.show()
        self.raise_()
        self._input.setFocus()
        _apply_dwm_blur(self)

        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()

        self._pos_anim.setStartValue(start)
        self._pos_anim.setEndValue(target)
        self._pos_anim.start()

    def dismiss(self) -> None:
        """Fade out and hide the overlay."""
        if not self.isVisible():
            return
        self._opacity_anim.stop()
        self._pos_anim.stop()
        try:
            self._opacity_anim.finished.disconnect(self._on_dismissed)
        except RuntimeError:
            pass
        self._opacity_anim.setStartValue(self.windowOpacity())
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.finished.connect(self._on_dismissed)
        self._opacity_anim.start()

    # -- Agent output slots --------------------------------------------------

    def on_token(self, token: str) -> None:
        """Append a streamed LLM token to the current running step pill."""
        if self._current_step_id is None:
            self._current_step_id = "step_auto"
            self._steps.add_step_pill(self._current_step_id, token, "running")
        else:
            pill = self._steps.get_step_pill(self._current_step_id)
            if pill:
                pill.set_text(pill._text_lbl.text() + token)

    def on_step_update(self, step_id: str, status: str, text: str) -> None:
        """Create or update a named step pill."""
        existing = self._steps.get_step_pill(step_id)
        if existing:
            existing.set_text(text)
            existing.set_status(status)
        else:
            self._steps.add_step_pill(step_id, text, status)
        self._current_step_id = step_id if status == "running" else None

    # -- Qt overrides --------------------------------------------------------

    def keyPressEvent(self, event: object) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:  # type: ignore[attr-defined]
            self.dismiss()
        else:
            super().keyPressEvent(event)  # type: ignore[arg-type]

    def eventFilter(  # type: ignore[override]
        self, obj: QObject, event: QEvent
    ) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and self.isVisible():
            if isinstance(event, QMouseEvent):
                if not self.geometry().contains(event.globalPosition().toPoint()):
                    self.dismiss()
        return super().eventFilter(obj, event)

    # -- Private -------------------------------------------------------------

    def _on_return(self) -> None:
        text = self._input.text().strip()
        if text:
            self._input.clear()
            self.instruction_submitted.emit(text)

    def _on_dismissed(self) -> None:
        try:
            self._opacity_anim.finished.disconnect(self._on_dismissed)
        except RuntimeError:
            pass
        self.hide()

    def _center_pos(self) -> QPoint:
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = rect.center().x() - self._WIDTH // 2
            y = rect.center().y() - 80
            return QPoint(x, y)
        return QPoint(100, 100)


# ---------------------------------------------------------------------------
# Visual demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    overlay = OverlayWindow()
    overlay.show_overlay()

    def _demo() -> None:
        overlay.on_step_update("s1", "running", "Scanning the screen for elements...")
        overlay.on_step_update("s2", "pending", "Waiting to click button")

        def _finish() -> None:
            overlay.on_step_update("s1", "done", "Found 3 elements on screen")
            overlay.on_step_update("s2", "running", "Clicking Submit button...")

        QTimer.singleShot(1200, _finish)

    QTimer.singleShot(400, _demo)
    sys.exit(app.exec())
