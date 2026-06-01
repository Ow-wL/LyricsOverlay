"""단축키 입력 위젯."""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtGui import QKeyEvent, QKeySequence  # type: ignore
from PySide6.QtWidgets import QLineEdit  # type: ignore

from gui.theme import UIConfig


class HotkeyEdit(QLineEdit):
    """클릭하면 키 입력 대기 상태로 전환되는 단축키 편집 위젯."""

    changed = Signal(str)

    def __init__(self, current_val: str, parent=None):
        super().__init__(parent)
        self.setText(current_val)
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.is_recording = False
        self.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 8px;
                border-radius: 8px;
                border: 1px solid {UIConfig.LIGHT_BORDER};
                background-color: transparent;
                font-weight: 700;
            }}
            QLineEdit:focus {{
                border: 2px solid #7C4DFF;
                background-color: rgba(124, 77, 255, 10%);
            }}
            """
        )

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self._start_recording()

    def _start_recording(self) -> None:
        self.is_recording = True
        self.setText("키 입력 대기 중...")
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.is_recording:
            return

        key = event.key()
        if key == Qt.Key_Escape:
            self._stop_recording(self.text())
            return

        modifiers = event.modifiers()
        combo: list[str] = []
        if modifiers & Qt.ControlModifier:
            combo.append("ctrl")
        if modifiers & Qt.ShiftModifier:
            combo.append("shift")
        if modifiers & Qt.AltModifier:
            combo.append("alt")
        if modifiers & Qt.MetaModifier:
            combo.append("win")

        key_text = QKeySequence(key).toString().lower()
        special_keys = {
            Qt.Key_Control: "",
            Qt.Key_Shift: "",
            Qt.Key_Alt: "",
            Qt.Key_Meta: "",
            Qt.Key_CapsLock: "caps lock",
            Qt.Key_NumLock: "num lock",
            Qt.Key_ScrollLock: "scroll lock",
            Qt.Key_Print: "print screen",
            Qt.Key_Pause: "pause",
            Qt.Key_Insert: "insert",
            Qt.Key_Delete: "delete",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "page up",
            Qt.Key_PageDown: "page down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Tab: "tab",
            Qt.Key_Space: "space",
        }

        key_name = special_keys.get(key, key_text)
        if key_name:
            if key_name not in combo:
                combo.append(key_name)
            final_hotkey = "+".join(combo)
            self._stop_recording(final_hotkey)
            self.changed.emit(final_hotkey)

    def focusOutEvent(self, event) -> None:
        if self.is_recording:
            self.is_recording = False
        super().focusOutEvent(event)

    def _stop_recording(self, val: str) -> None:
        self.is_recording = False
        self.setText(val)
        self.clearFocus()
