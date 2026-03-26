"""EdgeDesk reusable PyQt6 widget primitives.

All colors and radii use constants from ui.styles.theme — never hard-coded.
Run this file directly for a live visual demo: uv run python ui/styles/components.py
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

try:
    import qtawesome as qta
    _QTA = True
except ImportError:
    _QTA = False

from ui.styles.qss import button_qss, glass_card_qss, tab_button_qss
from ui.styles.theme import (
    ACCENT_ERROR,
    ACCENT_PRIMARY,
    ACCENT_SUCCESS,
    BG_ELEVATED,
    FONT_SIZE_BODY,
    RADIUS_MD,
    SPACE_2,
    SPACE_4,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

_STATUS_META: dict[str, tuple[str, str]] = {
    "pending": (TEXT_TERTIARY, "fa5s.circle"),
    "running": (ACCENT_PRIMARY, "fa5s.spinner"),
    "done":    (ACCENT_SUCCESS, "fa5s.check-circle"),
    "failed":  (ACCENT_ERROR,   "fa5s.times-circle"),
}


# ── GlassCard ────────────────────────────────────────────────────────────────

class GlassCard(QFrame):
    """Frosted-glass card — base container for all elevated surfaces."""

    def __init__(self, radius: int = RADIUS_MD, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setStyleSheet(glass_card_qss(radius))
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 128))
        self.setGraphicsEffect(shadow)


# ── StatusDot ────────────────────────────────────────────────────────────────

class StatusDot(QWidget):
    """8 x 8 px colored circle with an optional looping pulse animation."""

    def __init__(
        self, color: str = TEXT_TERTIARY, pulse: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._color = color
        self.__opacity: float = 1.0

        self._anim = QPropertyAnimation(self, b"dot_opacity", self)
        self._anim.setDuration(800)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.3)
        self._anim.setLoopCount(-1)
        if pulse:
            self._anim.start()

    @pyqtProperty(float)
    def dot_opacity(self) -> float:  # type: ignore[override]
        return self.__opacity

    @dot_opacity.setter  # type: ignore[override]
    def dot_opacity(self, v: float) -> None:
        self.__opacity = v
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def set_pulse(self, active: bool) -> None:
        if active:
            self._anim.start()
        else:
            self._anim.stop()
            self.__opacity = 1.0
            self.update()

    def paintEvent(self, _event: object) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self.__opacity)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(self._color)))
        p.drawEllipse(0, 0, 8, 8)
        p.end()


# ── AccentButton ─────────────────────────────────────────────────────────────

class AccentButton(QPushButton):
    """Primary (filled) or ghost (outlined) button using design token styles."""

    def __init__(
        self, text: str = "", variant: str = "primary", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(button_qss(variant))


# ── ToggleSwitch ──────────────────────────────────────────────────────────────

class ToggleSwitch(QAbstractButton):
    """Animated on/off toggle. Knob slides 200 ms via QPropertyAnimation."""

    _W: int = 44
    _H: int = 24
    _K: int = 20  # knob diameter

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(self._W, self._H)
        self.__t: float = 0.0
        self._anim = QPropertyAnimation(self, b"toggle_t", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.toggled.connect(self._on_toggled)

    @pyqtProperty(float)
    def toggle_t(self) -> float:  # type: ignore[override]
        return self.__t

    @toggle_t.setter  # type: ignore[override]
    def toggle_t(self, v: float) -> None:
        self.__t = v
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._anim.setStartValue(self.__t)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._W, self._H)

    def paintEvent(self, _event: object) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        h = self._H - 4
        track_col = QColor(ACCENT_PRIMARY) if self.isChecked() else QColor(BG_ELEVATED)
        p.setBrush(QBrush(track_col))
        p.drawRoundedRect(0, 2, self._W, h, h / 2, h / 2)
        travel = self._W - self._K - 4
        p.setBrush(QBrush(QColor(TEXT_PRIMARY)))
        p.drawEllipse(int(2 + self.__t * travel), 2, self._K, self._K)
        p.end()


# ── StepPill ─────────────────────────────────────────────────────────────────

class StepPill(QWidget):
    """Single agent-step entry: icon + text label + status dot."""

    def __init__(
        self, text: str = "", status: str = "pending", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_2, SPACE_2, SPACE_2, SPACE_2)
        layout.setSpacing(SPACE_2)

        self._icon_lbl = QLabel(self)
        self._icon_lbl.setFixedSize(16, 16)
        self._text_lbl = QLabel(text, self)
        self._dot = StatusDot(parent=self)

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl, 1)
        layout.addWidget(self._dot)

        self.set_status(status)

    def set_text(self, text: str) -> None:
        self._text_lbl.setText(text)

    def set_status(self, status: str) -> None:
        color, icon_name = _STATUS_META.get(status, (TEXT_TERTIARY, "fa5s.circle"))
        self._dot.set_color(color)
        self._dot.set_pulse(status == "running")
        self._text_lbl.setStyleSheet(f"color: {color};")
        if _QTA:
            self._icon_lbl.setPixmap(qta.icon(icon_name, color=color).pixmap(16, 16))
        bg = BG_ELEVATED if status != "pending" else "transparent"
        self.setStyleSheet(f"StepPill {{ background: {bg}; border-radius: {RADIUS_MD}px; }}")


# ── AnimatedTabBar ────────────────────────────────────────────────────────────

class AnimatedTabBar(QWidget):
    """Horizontal tab bar with a sliding ACCENT_PRIMARY underline indicator."""

    tab_changed: pyqtSignal = pyqtSignal(int)

    def __init__(self, tabs: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current = 0
        self.__ind_x: float = 0.0

        self._anim = QPropertyAnimation(self, b"indicator_x", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._btns: list[QPushButton] = []

        for i, label in enumerate(tabs):
            btn = QPushButton(label, self)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(tab_button_qss(active=(i == 0)))
            btn.clicked.connect(lambda _, idx=i: self.set_current(idx))
            row.addWidget(btn)
            self._btns.append(btn)

        row.addStretch()

    @pyqtProperty(float)
    def indicator_x(self) -> float:  # type: ignore[override]
        return self.__ind_x

    @indicator_x.setter  # type: ignore[override]
    def indicator_x(self, v: float) -> None:
        self.__ind_x = v
        self.update()

    def set_current(self, index: int, *, animate: bool = True) -> None:
        for i, btn in enumerate(self._btns):
            btn.setStyleSheet(tab_button_qss(active=(i == index)))
        self._current = index
        if self._btns:
            target = float(self._btns[index].pos().x())
            if animate:
                self._anim.setStartValue(self.__ind_x)
                self._anim.setEndValue(target)
                self._anim.start()
            else:
                self.__ind_x = target
        self.tab_changed.emit(index)

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        super().paintEvent(event)  # type: ignore[arg-type]
        if not self._btns or not (0 <= self._current < len(self._btns)):
            return
        p = QPainter(self)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(ACCENT_PRIMARY)))
        p.drawRect(int(self.__ind_x), self.height() - 2, self._btns[self._current].width(), 2)
        p.end()


# ── Visual demo ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QVBoxLayout

    from ui.styles.theme import BG_PRIMARY, SPACE_6, apply_font

    app = QApplication(sys.argv)
    apply_font(app)

    win = QWidget()
    win.setWindowTitle("EdgeDesk Component Demo")
    win.setStyleSheet(f"background: {BG_PRIMARY};")
    win.resize(680, 520)

    vbox = QVBoxLayout(win)
    vbox.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
    vbox.setSpacing(16)

    card = GlassCard()
    card.setMinimumHeight(60)
    vbox.addWidget(card)

    btn_row = QWidget()
    btn_layout = QHBoxLayout(btn_row)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.addWidget(AccentButton("Primary Action"))
    btn_layout.addWidget(AccentButton("Ghost Action", variant="ghost"))
    btn_layout.addStretch()
    vbox.addWidget(btn_row)

    vbox.addWidget(ToggleSwitch())

    for s in ("pending", "running", "done", "failed"):
        vbox.addWidget(StepPill(f"Step is {s}", status=s))

    vbox.addWidget(AnimatedTabBar(["General", "LLM", "Hotkeys", "Privacy"]))
    vbox.addStretch()

    win.show()
    sys.exit(app.exec())
