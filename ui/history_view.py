"""EdgeDesk execution history timeline.

Displays paginated execution rows grouped by date. Each row is expandable
to reveal the full step log. Feedback buttons emit signals; the caller
(main.py / Phase 9) writes the score to the database.
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    import qtawesome as qta  # type: ignore[import]

    _QTA = True
except ImportError:
    _QTA = False

from ui.styles.components import GlassCard, StatusDot, StepPill
from ui.styles.qss import scrollbar_qss
from ui.styles.theme import (
    ACCENT_ERROR,
    ACCENT_PRIMARY,
    ACCENT_SUCCESS,
    BG_PRIMARY,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_TITLE,
    GLASS_BG,
    GLASS_BORDER,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_4,
    SPACE_6,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

_STATUS_COLORS: dict[str, str] = {
    "success": ACCENT_SUCCESS,
    "failed": ACCENT_ERROR,
    "running": ACCENT_PRIMARY,
    "pending": TEXT_TERTIARY,
}


# ---------------------------------------------------------------------------
# HistoryRow
# ---------------------------------------------------------------------------


class HistoryRow(GlassCard):
    """Single execution row: click to expand the step log.

    Signals:
        feedback_given(str, int): execution_id, score (+1 or -1).
    """

    feedback_given: pyqtSignal = pyqtSignal(str, int)

    def __init__(self, execution_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("HistoryRow")
        self._exec_id: str = str(execution_data.get("id", ""))
        self._expanded: bool = False

        self.setStyleSheet(
            f"QFrame#HistoryRow {{"
            f"  background: {GLASS_BG};"
            f"  border: 1px solid {GLASS_BORDER};"
            f"  border-radius: {RADIUS_MD}px;"
            f"}}"
            f"QFrame#HistoryRow:hover {{ background: rgba(255,255,255,0.06); }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE_4, SPACE_2, SPACE_4, SPACE_2)
        outer.setSpacing(0)

        # Summary row
        summary = QHBoxLayout()
        summary.setSpacing(SPACE_2)

        started = execution_data.get("started_at", "")
        ts_lbl = QLabel(started[:16].replace("T", " ") if started else "—", self)
        ts_lbl.setStyleSheet(
            f"color: {TEXT_TERTIARY}; font-size: {FONT_SIZE_CAPTION}px;"
        )
        ts_lbl.setFixedWidth(100)

        rule_name = execution_data.get("rule_name", "Unknown")
        chip = QLabel(rule_name, self)
        chip.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;"
            f"background: {GLASS_BORDER}; border-radius: {RADIUS_SM}px;"
            f"padding: {SPACE_1}px {SPACE_2}px;"
        )

        status = str(execution_data.get("status", "failed"))
        dot = StatusDot(
            color=_STATUS_COLORS.get(status, TEXT_TERTIARY),
            pulse=(status == "running"),
            parent=self,
        )

        duration = execution_data.get("duration_seconds")
        dur_lbl = QLabel(f"{duration:.1f}s" if duration is not None else "—", self)
        dur_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;"
        )
        dur_lbl.setFixedWidth(40)

        up_btn = self._thumb_btn("fa5s.thumbs-up", +1)
        dn_btn = self._thumb_btn("fa5s.thumbs-down", -1)

        summary.addWidget(ts_lbl)
        summary.addWidget(chip)
        summary.addWidget(dot)
        summary.addWidget(dur_lbl)
        summary.addStretch()
        summary.addWidget(up_btn)
        summary.addWidget(dn_btn)
        outer.addLayout(summary)

        # Expandable step log
        self._step_container = QWidget(self)
        self._step_container.setMaximumHeight(0)
        self._step_container.setStyleSheet("background: transparent;")
        step_layout = QVBoxLayout(self._step_container)
        step_layout.setContentsMargins(0, SPACE_2, 0, 0)
        step_layout.setSpacing(4)

        for step in execution_data.get("steps_log") or []:
            pill = StepPill(
                text=str(step.get("text", "")),
                status=str(step.get("status", "done")),
                parent=self._step_container,
            )
            step_layout.addWidget(pill)

        outer.addWidget(self._step_container)

        self._expand_anim = QPropertyAnimation(
            self._step_container, b"maximumHeight", self
        )
        self._expand_anim.setDuration(150)
        self._expand_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def toggle_expand(self) -> None:
        """Expand or collapse the step log with animation."""
        if self._expanded:
            self._expand_anim.setStartValue(self._step_container.height())
            self._expand_anim.setEndValue(0)
            self._expanded = False
        else:
            hint = self._step_container.sizeHint().height()
            self._expand_anim.setStartValue(0)
            self._expand_anim.setEndValue(min(hint if hint > 0 else 120, 300))
            self._expanded = True
        self._expand_anim.start()

    def mousePressEvent(self, event: object) -> None:  # type: ignore[override]
        super().mousePressEvent(event)  # type: ignore[arg-type]
        self.toggle_expand()

    # -- Private -------------------------------------------------------------

    def _thumb_btn(self, icon_name: str, score: int) -> QPushButton:
        btn = QPushButton(self)
        btn.setFixedSize(24, 24)
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; }}"
            f"QPushButton:hover {{ background: {GLASS_BG}; border-radius: 4px; }}"
        )
        if _QTA:
            btn.setIcon(qta.icon(icon_name, color=TEXT_TERTIARY))
        btn.clicked.connect(lambda: self.feedback_given.emit(self._exec_id, score))
        return btn


# ---------------------------------------------------------------------------
# HistoryView
# ---------------------------------------------------------------------------


class HistoryView(QWidget):
    """Scrollable timeline of execution history rows.

    Signals:
        load_more_requested(int): Emitted when the user scrolls near the bottom.
                                   Argument is the current offset for pagination.
        feedback_given(str, int): Bubbled up from HistoryRow.
    """

    load_more_requested: pyqtSignal = pyqtSignal(int)
    feedback_given: pyqtSignal = pyqtSignal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        root.setSpacing(SPACE_4)

        title = QLabel("Execution History", self)
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_TITLE}px; font-weight: bold;"
        )
        root.addWidget(title)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }" + scrollbar_qss()
        )
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(SPACE_2)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, 1)

        self._total_loaded: int = 0
        self._loading: bool = False

    # -- Public API ----------------------------------------------------------

    def load_executions(
        self, executions: list[dict], *, append: bool = False
    ) -> None:
        """Populate (or append to) the timeline from a list of execution dicts.

        Expected keys: id, rule_name, started_at, status, duration_seconds,
        steps_log (list of {text, status}).
        """
        if not append:
            while self._content_layout.count() > 1:
                item = self._content_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            self._total_loaded = 0

        current_date: str | None = None
        insert_idx = max(0, self._content_layout.count() - 1)

        for exec_data in executions:
            started = str(exec_data.get("started_at", ""))
            date_str = started[:10] if len(started) >= 10 else "Unknown date"

            if date_str != current_date:
                current_date = date_str
                self._content_layout.insertWidget(
                    insert_idx, self._date_header(date_str)
                )
                insert_idx += 1

            row = HistoryRow(exec_data, parent=self._content)
            row.feedback_given.connect(self.feedback_given)
            self._content_layout.insertWidget(insert_idx, row)
            insert_idx += 1

        self._total_loaded += len(executions)
        self._loading = False

    # -- Private -------------------------------------------------------------

    def _date_header(self, date_str: str) -> QLabel:
        lbl = QLabel(date_str, self._content)
        lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;"
            f"background: {BG_PRIMARY}; padding: {SPACE_2}px 0;"
            f"font-weight: bold;"
        )
        return lbl

    def _on_scroll(self, value: int) -> None:
        if self._loading:
            return
        bar = self._scroll.verticalScrollBar()
        if bar.maximum() > 0 and value >= bar.maximum() - 100:
            self._loading = True
            self.load_more_requested.emit(self._total_loaded)
