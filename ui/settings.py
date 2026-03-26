"""EdgeDesk settings dialog.

640x480 modal dialog with four tabs: General, LLM, Hotkeys, Privacy.
Settings are persisted to the project .env file via python-dotenv.
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.styles.components import AccentButton, AnimatedTabBar, ToggleSwitch
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
    SPACE_1,
    SPACE_2,
    SPACE_4,
    SPACE_6,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)

try:
    from dotenv import dotenv_values, set_key  # type: ignore[import]

    _DOTENV = True
except ImportError:
    _DOTENV = False


# ---------------------------------------------------------------------------
# Shared QSS helpers (local to this module)
# ---------------------------------------------------------------------------

_COMBO_QSS: str = f"""
    QComboBox {{
        background: {GLASS_BG};
        border: 1px solid {GLASS_BORDER};
        border-radius: {RADIUS_SM}px;
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_BODY}px;
        padding: {SPACE_2}px {SPACE_4}px;
    }}
    QComboBox:hover {{ border-color: {ACCENT_PRIMARY}; }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background: {BG_ELEVATED};
        border: 1px solid {GLASS_BORDER};
        color: {TEXT_PRIMARY};
        selection-background-color: {ACCENT_PRIMARY};
    }}
"""

_SLIDER_QSS: str = f"""
    QSlider::groove:horizontal {{
        height: 4px;
        background: {GLASS_BORDER};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {ACCENT_PRIMARY};
        border: none;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{ background: {ACCENT_PRIMARY}; border-radius: 2px; }}
"""


# ---------------------------------------------------------------------------
# SettingsDialog
# ---------------------------------------------------------------------------


class SettingsDialog(QDialog):
    """Modal settings dialog — General | LLM | Hotkeys | Privacy tabs.

    Args:
        env_path: Override the ``.env`` file path. Defaults to the project root
                  ``.env``. Useful for testing.
    """

    hotkey_changed: pyqtSignal = pyqtSignal(str)
    clear_history_requested: pyqtSignal = pyqtSignal()
    export_data_requested: pyqtSignal = pyqtSignal()

    def __init__(
        self,
        env_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._env_file: Path = env_path or (Path(__file__).parent.parent / ".env")

        self.setWindowTitle("EdgeDesk Settings")
        self.setFixedSize(640, 480)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(f"background: {BG_PRIMARY}; color: {TEXT_PRIMARY};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Tab bar
        self._tabs = AnimatedTabBar(["General", "LLM", "Hotkeys", "Privacy"], self)
        self._tabs.setStyleSheet(f"background: {BG_SURFACE};")
        root.addWidget(self._tabs)

        # Content pages
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_general_tab())
        self._stack.addWidget(self._build_llm_tab())
        self._stack.addWidget(self._build_hotkeys_tab())
        self._stack.addWidget(self._build_privacy_tab())
        root.addWidget(self._stack, 1)
        self._tabs.tab_changed.connect(self._stack.setCurrentIndex)

        # Bottom button row
        footer = QHBoxLayout()
        footer.setContentsMargins(SPACE_6, SPACE_4, SPACE_6, SPACE_4)
        save_btn = AccentButton("Save Changes", parent=self)
        save_btn.clicked.connect(self._save_settings)
        close_btn = AccentButton("Close", variant="ghost", parent=self)
        close_btn.clicked.connect(self.accept)
        footer.addStretch()
        footer.addWidget(save_btn)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        self._load_settings()

    # -- Tab builders --------------------------------------------------------

    def _build_general_tab(self) -> QWidget:
        page = self._page()
        layout = page.layout()
        assert layout is not None

        layout.addWidget(self._section_lbl("Data Directory"))
        data_lbl = QLabel(str(Path.home() / ".edgedesk"), page)
        data_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}px;"
            f"background: {GLASS_BG}; border: 1px solid {GLASS_BORDER};"
            f"border-radius: {RADIUS_SM}px; padding: {SPACE_2}px {SPACE_4}px;"
        )
        layout.addWidget(data_lbl)

        layout.addSpacing(SPACE_4)
        layout.addWidget(self._section_lbl("Auto-start on boot"))
        self._autostart_toggle = ToggleSwitch(parent=page)
        layout.addWidget(self._autostart_toggle)

        layout.addStretch()
        return page

    def _build_llm_tab(self) -> QWidget:
        page = self._page()
        layout = page.layout()
        assert layout is not None

        layout.addWidget(self._section_lbl("Model"))
        self._model_edit = QLineEdit(page)
        self._model_edit.setPlaceholderText("mistral-nemo")
        self._model_edit.setStyleSheet(input_field_qss())
        layout.addWidget(self._model_edit)

        layout.addSpacing(SPACE_2)
        layout.addWidget(self._section_lbl("Ollama Base URL"))
        self._base_url_edit = QLineEdit(page)
        self._base_url_edit.setPlaceholderText("http://localhost:11434")
        self._base_url_edit.setStyleSheet(input_field_qss())
        layout.addWidget(self._base_url_edit)

        layout.addSpacing(SPACE_2)
        layout.addWidget(self._section_lbl("Context Window (num_ctx)"))
        ctx_row = QHBoxLayout()
        self._ctx_slider = QSlider(Qt.Orientation.Horizontal, page)
        self._ctx_slider.setRange(1024, 8192)
        self._ctx_slider.setSingleStep(1024)
        self._ctx_slider.setPageStep(1024)
        self._ctx_slider.setStyleSheet(_SLIDER_QSS)
        self._ctx_lbl = QLabel("4096", page)
        self._ctx_lbl.setFixedWidth(48)
        self._ctx_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._ctx_slider.valueChanged.connect(lambda v: self._ctx_lbl.setText(str(v)))
        ctx_row.addWidget(self._ctx_slider, 1)
        ctx_row.addWidget(self._ctx_lbl)
        layout.addLayout(ctx_row)

        layout.addStretch()
        return page

    def _build_hotkeys_tab(self) -> QWidget:
        page = self._page()
        layout = page.layout()
        assert layout is not None

        layout.addWidget(self._section_lbl("Overlay Hotkey"))
        self._hotkey_edit = QKeySequenceEdit(page)
        self._hotkey_edit.setStyleSheet(
            f"QKeySequenceEdit {{"
            f"  background: {GLASS_BG}; border: 1px solid {GLASS_BORDER};"
            f"  border-radius: {RADIUS_SM}px; color: {TEXT_PRIMARY};"
            f"  font-size: {FONT_SIZE_BODY}px; padding: {SPACE_2}px {SPACE_4}px;"
            f"}}"
        )
        layout.addWidget(self._hotkey_edit)
        hint = QLabel("Default: Alt+Space", page)
        hint.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: {FONT_SIZE_CAPTION}px;")
        layout.addWidget(hint)

        layout.addStretch()
        return page

    def _build_privacy_tab(self) -> QWidget:
        page = self._page()
        layout = page.layout()
        assert layout is not None

        layout.addWidget(self._section_lbl("Data Management"))

        clear_btn = AccentButton("Clear All History", variant="ghost", parent=page)
        clear_btn.clicked.connect(self.clear_history_requested.emit)
        layout.addWidget(clear_btn)

        layout.addSpacing(SPACE_2)
        export_btn = AccentButton("Export Data", variant="ghost", parent=page)
        export_btn.clicked.connect(self.export_data_requested.emit)
        layout.addWidget(export_btn)

        layout.addStretch()
        return page

    # -- Settings I/O --------------------------------------------------------

    def _load_settings(self) -> None:
        """Populate form fields from .env file."""
        values: dict[str, str | None] = {}
        if _DOTENV and self._env_file.exists():
            try:
                values = dotenv_values(str(self._env_file))  # type: ignore[assignment]
            except Exception:
                pass

        self._model_edit.setText(values.get("OLLAMA_MODEL") or "mistral-nemo")
        self._base_url_edit.setText(
            values.get("OLLAMA_BASE_URL") or "http://localhost:11434"
        )
        try:
            self._ctx_slider.setValue(int(values.get("NUM_CTX") or 4096))
        except (ValueError, TypeError):
            self._ctx_slider.setValue(4096)

        from PyQt6.QtGui import QKeySequence

        raw_hotkey = values.get("OVERLAY_HOTKEY") or "alt+space"
        self._hotkey_edit.setKeySequence(QKeySequence(raw_hotkey.title()))

    def _save_settings(self) -> None:
        """Persist form field values to .env file."""
        if not _DOTENV:
            return
        try:
            path = str(self._env_file)
            set_key(path, "OLLAMA_MODEL", self._model_edit.text().strip() or "mistral-nemo")
            set_key(path, "OLLAMA_BASE_URL", self._base_url_edit.text().strip())
            set_key(path, "NUM_CTX", str(self._ctx_slider.value()))
            hotkey_raw = self._hotkey_edit.keySequence().toString()
            if hotkey_raw:
                normalized = hotkey_raw.lower().replace(" ", "")
                set_key(path, "OVERLAY_HOTKEY", normalized)
                self.hotkey_changed.emit(normalized)
        except Exception:
            pass  # Settings save is non-fatal

    # -- Private helpers -----------------------------------------------------

    def _page(self) -> QWidget:
        """Create a blank tab page with standard padding."""
        page = QWidget(self)
        page.setStyleSheet(f"background: {BG_PRIMARY};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_4)
        layout.setSpacing(SPACE_2)
        return page

    def _section_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;"
            f"text-transform: uppercase; letter-spacing: 0.5px;"
        )
        return lbl
