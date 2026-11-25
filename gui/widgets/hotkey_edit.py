"""단축키 입력 위젯."""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtGui import QKeyEvent, QKeySequence  # type: ignore
from PySide6.QtWidgets import QLineEdit  # type: ignore

_RECORDING_TEXT = "키 조합을 누르세요…"

_PRETTY = {
    "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win",
    "left": "←", "right": "→", "up": "↑", "down": "↓",
    "page up": "PgUp", "page down": "PgDn", "space": "Space", "enter": "Enter",
}


def pretty_hotkey(hotkey: str) -> str:
    """'ctrl+shift+right' → 'Ctrl + Shift + →' (빈 값은 '없음')."""
    if not hotkey:
        return "없음"
    parts = [p.strip() for p in hotkey.split("+") if p.strip()]
    return " + ".join(_PRETTY.get(p.lower(), p.upper() if len(p) <= 3 else p.title()) for p in parts)


class HotkeyEdit(QLineEdit):
    """클릭(또는 Enter/Space)하면 키 입력 대기 상태가 되는 단축키 편집 위젯.

    녹화 중: 조합 키를 누르면 확정, Esc는 취소, Backspace는 단축키 해제.
    확정된 값은 changed(str)로 알리며, 화면에는 읽기 쉬운 형태로 보여 줍니다.
    """

    changed = Signal(str)

    def __init__(self, current_val: str, parent=None):
        super().__init__(parent)
        self.value = current_val or ""
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setToolTip("클릭한 뒤 키 조합을 누르세요 · Esc 취소 · Backspace 해제")
        self.is_recording = False
        self.setObjectName("HotkeyEdit")  # 색은 전역 스타일시트에서
        self._show_value()

    def set_value(self, value: str) -> None:
        """신호 없이 값을 바꿉니다 (검증 실패 시 되돌리기 등)."""
        self.value = value or ""
        self.is_recording = False
        self._show_value()

    def _show_value(self) -> None:
        self.setText(pretty_hotkey(self.value))

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self._start_recording()

    def _start_recording(self) -> None:
        self.is_recording = True
        self.setText(_RECORDING_TEXT)
        self.setFocus()

    def _cancel(self) -> None:
        self.is_recording = False
        self._show_value()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if not self.is_recording:
            if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
                self._start_recording()
            else:
                super().keyPressEvent(event)  # Tab 이동 등
            return

        if key == Qt.Key_Escape:
            self._cancel()
            return
        if key == Qt.Key_Backspace and not event.modifiers():
            self.is_recording = False
            self.value = ""
            self._show_value()
            self.changed.emit("")
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
            self.is_recording = False
            self.value = final_hotkey
            self._show_value()
            self.changed.emit(final_hotkey)

    def focusOutEvent(self, event) -> None:
        if self.is_recording:
            self._cancel()
        super().focusOutEvent(event)
