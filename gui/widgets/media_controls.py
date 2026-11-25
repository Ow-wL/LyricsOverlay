"""이전 곡 / 재생·일시정지 / 다음 곡 버튼 묶음.

버튼을 누르면 Windows 미디어 키를 보내므로, 미디어 키에 반응하는 플레이어(멜론 등)가 제어됩니다.
"""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget  # type: ignore

from core.hotkey_manager import send_next_track, send_play_pause, send_prev_track

_BUTTONS = (
    ("prev", "⏮", "이전 곡", send_prev_track),
    ("play_pause", "⏯", "재생 / 일시정지", send_play_pause),
    ("next", "⏭", "다음 곡", send_next_track),
)

_OVERLAY_STYLE = """
QPushButton {
    background-color: rgba(0, 0, 0, 150);
    color: white;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 15px;
    font-family: 'Segoe UI Symbol';
    font-size: 14px;
    padding: 0px;
}
QPushButton:hover { background-color: rgba(255, 255, 255, 60); }
QPushButton:pressed { background-color: rgba(255, 255, 255, 110); }
"""

# 앱 쪽은 테마 스타일시트를 따르고, 글꼴과 여백만 맞춥니다.
_APP_STYLE = "font-family: 'Segoe UI Symbol'; font-size: 18px; padding: 0px;"


class MediaControls(QWidget):
    """미디어 제어 버튼 3개. `variant`는 "app"(대시보드) 또는 "overlay"."""

    action_triggered = Signal(str)  # "prev" / "play_pause" / "next"

    def __init__(self, variant: str = "app", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if variant == "overlay" else 10)

        size = (30, 30) if variant == "overlay" else (56, 40)
        if variant == "overlay":
            self.setStyleSheet(_OVERLAY_STYLE)
            self.setAttribute(Qt.WA_TranslucentBackground)

        for key, glyph, tooltip, send in _BUTTONS:
            btn = QPushButton(glyph)
            btn.setFixedSize(*size)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            if variant != "overlay":
                btn.setStyleSheet(_APP_STYLE)
            btn.clicked.connect(lambda _=False, k=key, fn=send: self._trigger(k, fn))
            layout.addWidget(btn)

        self.adjustSize()

    def _trigger(self, key: str, send) -> None:
        send()
        self.action_triggered.emit(key)
