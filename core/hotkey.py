"""HotkeyManager — thread-safe global hotkey using the ``keyboard`` library.

The ``keyboard`` library fires callbacks from a background thread.
``QCoreApplication.postEvent`` is used to safely marshal the call to the
Qt main thread without touching any Qt object from the foreign thread.
"""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, QObject, pyqtSignal

try:
    import keyboard as _kb  # type: ignore[import]

    _KB_AVAILABLE: bool = True
except ImportError:
    _kb = None  # type: ignore[assignment]
    _KB_AVAILABLE = False


# Registered lazily so the module can be imported before QCoreApplication exists.
_HOTKEY_EVENT_ID: int = 0


def _hotkey_event_type() -> int:
    global _HOTKEY_EVENT_ID
    if _HOTKEY_EVENT_ID == 0:
        _HOTKEY_EVENT_ID = QEvent.registerEventType()
    return _HOTKEY_EVENT_ID


class _HotkeyEvent(QEvent):
    """Private event posted to the main thread when the hotkey fires."""

    def __init__(self) -> None:
        super().__init__(QEvent.Type(_hotkey_event_type()))


class HotkeyManager(QObject):
    """Registers a global hotkey and emits ``hotkey_triggered`` on the Qt main thread.

    Usage::

        manager = HotkeyManager("alt+space")
        manager.hotkey_triggered.connect(overlay.show_overlay)
        manager.register()
        # ...
        manager.unregister()
    """

    hotkey_triggered: pyqtSignal = pyqtSignal()

    def __init__(self, hotkey: str = "alt+space", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hotkey = hotkey
        self._registered: bool = False

    def register(self) -> None:
        """Register the global hotkey. Call once after QApplication is created."""
        if self._registered or not _KB_AVAILABLE:
            return
        _kb.add_hotkey(self._hotkey, self._fire, suppress=True)
        self._registered = True

    def unregister(self) -> None:
        """Unregister the global hotkey."""
        if not self._registered or not _KB_AVAILABLE:
            return
        try:
            _kb.remove_hotkey(self._hotkey)
        except Exception:
            pass
        self._registered = False

    # -- Private -------------------------------------------------------------

    def _fire(self) -> None:
        """Called from keyboard listener thread — post to main thread via Qt event."""
        QCoreApplication.postEvent(self, _HotkeyEvent())

    def event(self, e: QEvent) -> bool:  # type: ignore[override]
        if e.type() == QEvent.Type(_hotkey_event_type()):
            self.hotkey_triggered.emit()
            return True
        return super().event(e)
