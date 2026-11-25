"""이전 곡 / 재생·일시정지 / 다음 곡 버튼 묶음.

버튼을 누르면 Windows 미디어 키를 보내므로, 미디어 키에 반응하는 플레이어(멜론 등)가 제어됩니다.
"""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget  # type: ignore

from core.hotkey_manager import send_next_track, send_play_pause, send_prev_track
from gui import icons

_BUTTONS = (
    ("prev", icons.PREV, "이전 곡", send_prev_track),
    ("play_pause", icons.PLAY_PAUSE, "재생 / 일시정지", send_play_pause),
    ("next", icons.NEXT, "다음 곡", send_next_track),
)

# 오버레이는 앱 테마와 무관하게 어두운 반투명 유리로 표시합니다.
_OVERLAY_STYLE = f"""
QPushButton {{
    background-color: rgba(255, 255, 255, 38);
    color: white;
    border: 1px solid rgba(255, 255, 255, 70);
    border-radius: 15px;
    font-family: {icons.ICON_FONT_CSS};
    font-size: 12px;
    padding: 0px;
}}
QPushButton:hover {{ background-color: rgba(255, 255, 255, 80); }}
QPushButton:pressed {{ background-color: rgba(255, 255, 255, 130); }}
QPushButton#Main {{ background-color: rgba(120, 100, 255, 190); border: none; }}
QPushButton#Main:hover {{ background-color: rgba(140, 122, 255, 230); }}
"""


class MediaControls(QWidget):
    """미디어 제어 버튼 3개. `variant`는 "app"(대시보드) 또는 "overlay"."""

    action_triggered = Signal(str)  # "prev" / "play_pause" / "next"

    def __init__(self, variant: str = "app", parent=None):
        super().__init__(parent)
        overlay = variant == "overlay"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if overlay else 14)
        layout.setAlignment(Qt.AlignCenter)

        if overlay:
            self.setStyleSheet(_OVERLAY_STYLE)
            self.setAttribute(Qt.WA_TranslucentBackground)

        for key, glyph, tooltip, send in _BUTTONS:
            is_main = key == "play_pause"
            btn = QPushButton(glyph)
            if overlay:
                btn.setFixedSize(30, 30)
                if is_main:
                    btn.setObjectName("Main")
            else:
                btn.setObjectName("MediaButtonMain" if is_main else "MediaButton")
                btn.setFixedSize(*((48, 48) if is_main else (40, 40)))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _=False, k=key, fn=send: self._trigger(k, fn))
            layout.addWidget(btn)

        self.adjustSize()

    def _trigger(self, key: str, send) -> None:
        send()
        self.action_triggered.emit(key)
