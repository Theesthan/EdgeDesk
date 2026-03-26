"""EdgeDesk rule manager panel.

Split layout: left list of rule cards, right slide-in detail editor.
All mutations (save, delete, toggle) emit signals; main.py wires them to the DB.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.styles.components import AccentButton, GlassCard, ToggleSwitch
from ui.styles.qss import input_field_qss, scrollbar_qss
from ui.styles.theme import (
    ACCENT_PRIMARY,
    BG_ELEVATED,
    BG_PRIMARY,
    BG_SURFACE,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_TITLE,
    GLASS_BG,
    GLASS_BORDER,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_2,
    SPACE_4,
    SPACE_6,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

_TRIGGER_LABELS: dict[str, str] = {
    "time_cron": "Cron",
    "file_event": "File",
    "manual": "Manual",
}

_COMBO_QSS: str = (
    f"QComboBox {{ background: {GLASS_BG}; border: 1px solid {GLASS_BORDER};"
    f"border-radius: {RADIUS_SM}px; color: {TEXT_PRIMARY};"
    f"font-size: {FONT_SIZE_BODY}px; padding: {SPACE_2}px {SPACE_4}px; }}"
    f"QComboBox:hover {{ border-color: {ACCENT_PRIMARY}; }}"
    f"QComboBox::drop-down {{ border: none; }}"
    f"QComboBox QAbstractItemView {{ background: {BG_ELEVATED};"
    f"border: 1px solid {GLASS_BORDER}; color: {TEXT_PRIMARY};"
    f"selection-background-color: {ACCENT_PRIMARY}; }}"
)

_PLAIN_QSS: str = (
    f"QPlainTextEdit {{ background: {GLASS_BG}; border: 1px solid {GLASS_BORDER};"
    f"border-radius: {RADIUS_SM}px; color: {TEXT_PRIMARY};"
    f"font-size: {FONT_SIZE_BODY}px; padding: {SPACE_2}px; }}"
    f"QPlainTextEdit:focus {{ border-color: {ACCENT_PRIMARY}; }}"
)


# ---------------------------------------------------------------------------
# RuleCard
# ---------------------------------------------------------------------------


class RuleCard(GlassCard):
    """Individual rule card shown in the left panel list.

    Signals:
        clicked(str):        rule_id — user clicked the card body.
        toggled(str, bool):  rule_id, new enabled state.
    """

    clicked: pyqtSignal = pyqtSignal(str)
    toggled: pyqtSignal = pyqtSignal(str, bool)

    def __init__(self, rule_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("RuleCard")
        self._rule_id: str = str(rule_data.get("id", ""))

        self.setStyleSheet(
            f"QFrame#RuleCard {{ background: {GLASS_BG}; border: 1px solid {GLASS_BORDER};"
            f"border-radius: {RADIUS_MD}px; }}"
            f"QFrame#RuleCard:hover {{ background: {BG_ELEVATED};"
            f"border-left: 2px solid {ACCENT_PRIMARY}; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_2, SPACE_4, SPACE_2)
        layout.setSpacing(SPACE_2)

        # Name + trigger badge (stacked vertically)
        info = QVBoxLayout()
        info.setSpacing(4)

        name_lbl = QLabel(str(rule_data.get("name", "Unnamed")), self)
        name_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_BODY}px;")

        trigger_type = str(rule_data.get("trigger_type", "manual"))
        badge = QLabel(_TRIGGER_LABELS.get(trigger_type, trigger_type), self)
        badge.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;"
            f"background: {GLASS_BORDER}; border-radius: {RADIUS_SM}px;"
            f"padding: {SPACE_2}px {SPACE_4}px;"
        )

        info.addWidget(name_lbl)
        info.addWidget(badge)

        # Run count
        run_count = rule_data.get("run_count", 0)
        count_lbl = QLabel(f"{run_count} runs", self)
        count_lbl.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_SIZE_CAPTION}px;")

        # Toggle switch
        self._toggle = ToggleSwitch(parent=self)
        self._toggle.setChecked(bool(rule_data.get("enabled", True)))
        self._toggle.toggled.connect(lambda checked: self.toggled.emit(self._rule_id, checked))

        layout.addLayout(info, 1)
        layout.addWidget(count_lbl)
        layout.addWidget(self._toggle)

    def mousePressEvent(self, event: object) -> None:  # type: ignore[override]
        super().mousePressEvent(event)  # type: ignore[arg-type]
        self.clicked.emit(self._rule_id)


# ---------------------------------------------------------------------------
# RuleDetailEditor
# ---------------------------------------------------------------------------


class RuleDetailEditor(QWidget):
    """Form for creating or editing a single rule.

    Signals:
        saved(dict):    Emitted with the full rule data dict on save.
        deleted(str):   Emitted with rule_id on delete.
    """

    saved: pyqtSignal = pyqtSignal(dict)
    deleted: pyqtSignal = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rule_id: str | None = None
        self.setStyleSheet(f"background: {BG_SURFACE};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_4, SPACE_6, SPACE_4)
        layout.setSpacing(SPACE_2)

        self._title_lbl = QLabel("New Rule", self)
        self._title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_TITLE}px; font-weight: bold;"
        )
        layout.addWidget(self._title_lbl)

        layout.addWidget(self._cap("Name"))
        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("Rule name")
        self._name_edit.setStyleSheet(input_field_qss())
        layout.addWidget(self._name_edit)

        layout.addWidget(self._cap("Instruction"))
        self._instr_edit = QLineEdit(self)
        self._instr_edit.setPlaceholderText("Natural language task for the agent")
        self._instr_edit.setStyleSheet(input_field_qss())
        layout.addWidget(self._instr_edit)

        layout.addWidget(self._cap("Trigger Type"))
        self._trigger_combo = QComboBox(self)
        for key, label in _TRIGGER_LABELS.items():
            self._trigger_combo.addItem(label, key)
        self._trigger_combo.setStyleSheet(_COMBO_QSS)
        layout.addWidget(self._trigger_combo)

        layout.addWidget(self._cap("Trigger Config (JSON)"))
        self._config_edit = QPlainTextEdit(self)
        self._config_edit.setPlaceholderText('{"minute": "*/30"}')
        self._config_edit.setMaximumHeight(80)
        self._config_edit.setStyleSheet(_PLAIN_QSS)
        layout.addWidget(self._config_edit)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self._save_btn = AccentButton("Save Rule", parent=self)
        self._save_btn.clicked.connect(self._on_save)
        self._delete_btn = AccentButton("Delete", variant="ghost", parent=self)
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def load_rule(self, rule_data: dict | None) -> None:
        """Populate the form for an existing rule, or reset for a new one."""
        if rule_data is None:
            self._rule_id = None
            self._title_lbl.setText("New Rule")
            self._name_edit.clear()
            self._instr_edit.clear()
            self._config_edit.clear()
            self._trigger_combo.setCurrentIndex(0)
            self._delete_btn.setVisible(False)
        else:
            self._rule_id = str(rule_data.get("id", ""))
            self._title_lbl.setText(str(rule_data.get("name", "Edit Rule")))
            self._name_edit.setText(str(rule_data.get("name", "")))
            self._instr_edit.setText(str(rule_data.get("instruction", "")))
            trigger_type = str(rule_data.get("trigger_type", "manual"))
            for i in range(self._trigger_combo.count()):
                if self._trigger_combo.itemData(i) == trigger_type:
                    self._trigger_combo.setCurrentIndex(i)
                    break
            config = rule_data.get("trigger_config") or {}
            self._config_edit.setPlainText(json.dumps(config, indent=2) if config else "")
            self._delete_btn.setVisible(True)

    # -- Private -------------------------------------------------------------

    def _cap(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;")
        return lbl

    def _on_save(self) -> None:
        config_text = self._config_edit.toPlainText().strip()
        try:
            config: dict = json.loads(config_text) if config_text else {}
        except json.JSONDecodeError:
            config = {}

        self.saved.emit(
            {
                "id": self._rule_id,
                "name": self._name_edit.text().strip(),
                "instruction": self._instr_edit.text().strip(),
                "trigger_type": self._trigger_combo.currentData(),
                "trigger_config": config,
            }
        )

    def _on_delete(self) -> None:
        if self._rule_id:
            self.deleted.emit(self._rule_id)


# ---------------------------------------------------------------------------
# RuleManagerPanel
# ---------------------------------------------------------------------------


class RuleManagerPanel(QWidget):
    """Split-pane rule manager: left list + right slide-in editor.

    Signals:
        rule_saved(dict):        Bubbled from RuleDetailEditor.
        rule_deleted(str):       Bubbled from RuleDetailEditor.
        rule_toggled(str, bool): Bubbled from RuleCard toggle.
    """

    rule_saved: pyqtSignal = pyqtSignal(dict)
    rule_deleted: pyqtSignal = pyqtSignal(str)
    rule_toggled: pyqtSignal = pyqtSignal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        self._rule_data: dict[str, dict] = {}

        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Left panel
        left = QWidget(self)
        left.setFixedWidth(320)
        left.setStyleSheet(f"background: {BG_SURFACE}; border-right: 1px solid {GLASS_BORDER};")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        left_layout.setSpacing(SPACE_2)

        hdr = QHBoxLayout()
        title_lbl = QLabel("Rules", left)
        title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_TITLE}px; font-weight: bold;"
        )
        add_btn = AccentButton("+ New", parent=left)
        add_btn.setFixedHeight(32)
        add_btn.clicked.connect(self._on_new_rule)
        hdr.addWidget(title_lbl, 1)
        hdr.addWidget(add_btn)
        left_layout.addLayout(hdr)

        scroll = QScrollArea(left)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }" + scrollbar_qss()
        )
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(SPACE_2)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_container)
        left_layout.addWidget(scroll, 1)
        main.addWidget(left)

        # Right panel (absolute-positioned children for slide animation)
        self._right = QWidget(self)
        self._right.setStyleSheet(f"background: {BG_PRIMARY};")
        main.addWidget(self._right, 1)

        self._empty_lbl = QLabel("Select a rule to edit,\nor create a new one.", self._right)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_SIZE_BODY}px;")

        self._detail = RuleDetailEditor(self._right)
        self._detail.saved.connect(self.rule_saved)
        self._detail.deleted.connect(self._on_rule_deleted)
        self._detail.hide()

        self._slide_anim = QPropertyAnimation(self._detail, b"pos", self)
        self._slide_anim.setDuration(200)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def load_rules(self, rules: list[dict]) -> None:
        """Populate the left panel with rule cards."""
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._rule_data.clear()

        for rule_data in rules:
            rule_id = str(rule_data.get("id", ""))
            self._rule_data[rule_id] = rule_data
            card = RuleCard(rule_data, parent=self._cards_container)
            card.clicked.connect(self._on_card_clicked)
            card.toggled.connect(self.rule_toggled)
            self._cards_layout.insertWidget(max(0, self._cards_layout.count() - 1), card)

    # -- Qt overrides --------------------------------------------------------

    def resizeEvent(self, event: object) -> None:  # type: ignore[override]
        super().resizeEvent(event)  # type: ignore[arg-type]
        w, h = self._right.width(), self._right.height()
        self._empty_lbl.setGeometry(0, 0, w, h)
        if self._detail.isVisible():
            self._detail.setGeometry(0, 0, w, h)

    # -- Private -------------------------------------------------------------

    def _on_new_rule(self) -> None:
        self._show_detail(None)

    def _on_card_clicked(self, rule_id: str) -> None:
        self._show_detail(self._rule_data.get(rule_id))

    def _show_detail(self, rule_data: dict | None) -> None:
        w, h = self._right.width(), self._right.height()
        self._detail.load_rule(rule_data)
        self._detail.setGeometry(w, 0, w, h)
        self._empty_lbl.hide()
        self._detail.show()
        self._slide_anim.setStartValue(QPoint(w, 0))
        self._slide_anim.setEndValue(QPoint(0, 0))
        self._slide_anim.start()

    def _on_rule_deleted(self, rule_id: str) -> None:
        self.rule_deleted.emit(rule_id)
        self._detail.hide()
        self._empty_lbl.show()
