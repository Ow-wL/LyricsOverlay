import sys

import win32con
import win32gui
from PySide6.QtCore import Qt, QPoint  # type: ignore
from PySide6.QtGui import QColor, QFont  # type: ignore
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget  # type: ignore

from overlay.config_manager import OverlayConfigManager
from overlay.outlined_label import OutlinedLabel


class LyricsOverlay(QWidget):
    """화면 위에 항상 표시되는 가사 오버레이 창."""

    def __init__(self, config: OverlayConfigManager | None = None):
        super().__init__()
        self.config = config if config else OverlayConfigManager()
        self.bg_color: QColor = self.config.bg_color
        self.move_enabled: bool = self.config.move_enabled
        self.resize_enabled: bool = self.config.resize_enabled
        self._init_ui()
        self.sync_with_config()

    # ------------------------------------------------------------------ #
    # 초기화
    # ------------------------------------------------------------------ #

    def _init_ui(self) -> None:
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("LyricsBgFrame")
        self._update_bg_style()
        main_layout.addWidget(self.bg_frame)

        self.frame_layout = QVBoxLayout(self.bg_frame)
        self.frame_layout.setSpacing(5)

        self.song_info_label = OutlinedLabel("")
        self.song_info_label.setAlignment(Qt.AlignCenter)
        self.song_info_label.setStyleSheet("background: transparent;")
        self.song_info_label.hide()

        self.curr_label = OutlinedLabel("아직 가사 대기 중...")
        self.curr_label.setAlignment(Qt.AlignCenter)
        self.curr_label.setStyleSheet("background: transparent;")

        self.next_label = OutlinedLabel("다음 가사...")
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setStyleSheet("background: transparent;")

        self.frame_layout.addWidget(self.song_info_label)
        self.frame_layout.addWidget(self.curr_label)
        self.frame_layout.addWidget(self.next_label)

        self.setGeometry(
            self.config.x, self.config.y, self.config.width, self.config.height
        )

        self.resizing = False
        self.resize_margin = 15
        self.old_pos = QPoint()

    # ------------------------------------------------------------------ #
    # 설정 동기화
    # ------------------------------------------------------------------ #

    def sync_with_config(self) -> None:
        """매니저의 현재 설정을 UI에 동기화합니다."""
        self.apply_settings(self.config.get_settings())

    def _update_bg_style(self) -> None:
        c = self.bg_color
        self.bg_frame.setStyleSheet(
            f"""
            QFrame#LyricsBgFrame {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()});
                border-radius: 15px;
                border: none;
            }}
            """
        )

    def apply_settings(self, settings: dict) -> None:
        """settings dict를 받아 오버레이 외관과 동작을 갱신합니다."""
        if not settings.get("visible", True):
            self.hide()
            return
        self.show()

        if "bg_color" in settings:
            self.bg_color = settings["bg_color"]
            self._update_bg_style()

        x = settings.get("x", self.x())
        y = settings.get("y", self.y())
        w = settings.get("width", self.width())
        h = settings.get("height", self.height())
        self.setGeometry(x, y, w, h)

        font: QFont = settings.get("font", self.curr_label.font())
        text_color: QColor = settings.get("text_color", self.curr_label.text_color)
        out_color: QColor = settings.get("out_color", self.curr_label.outline_color)
        out_width: int = settings.get("out_width", self.curr_label.outline_width)

        self.curr_label.set_style(font, text_color, out_color, out_width)

        next_font = QFont(font)
        next_font.setPointSize(max(8, font.pointSize() - 6))
        self.next_label.set_style(
            next_font,
            QColor(text_color.red(), text_color.green(), text_color.blue(), 180),
            out_color,
            max(0, out_width - 1),
        )

        if "ghost" in settings:
            self.set_ghost_mode(settings["ghost"])
        if "move_enabled" in settings:
            self.move_enabled = settings["move_enabled"]
        if "resize_enabled" in settings:
            self.resize_enabled = settings["resize_enabled"]
        if "show_song_info" in settings:
            if settings["show_song_info"]:
                self.song_info_label.show()
            else:
                self.song_info_label.hide()

        # 곡 정보 레이블 폰트 (curr 보다 작게)
        info_font = QFont(font)
        info_font.setPointSize(max(7, font.pointSize() - 8))
        self.song_info_label.set_style(
            info_font,
            QColor(text_color.red(), text_color.green(), text_color.blue(), 160),
            out_color,
            max(0, out_width - 1),
        )

    # ------------------------------------------------------------------ #
    # 공개 메서드
    # ------------------------------------------------------------------ #

    def set_ghost_mode(self, enable: bool) -> None:
        """Win32 WS_EX_TRANSPARENT으로 클릭 통과 여부를 전환합니다."""
        hwnd = self.winId()
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if enable:
            win32gui.SetWindowLong(
                hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_TRANSPARENT
            )
        else:
            win32gui.SetWindowLong(
                hwnd, win32con.GWL_EXSTYLE, ex_style & ~win32con.WS_EX_TRANSPARENT
            )

    def set_move_enabled(self, enabled: bool) -> None:
        self.move_enabled = enabled
        if not enabled and not self.resize_enabled:
            self.setCursor(Qt.ArrowCursor)

    def set_resize_enabled(self, enabled: bool) -> None:
        self.resize_enabled = enabled
        if not enabled and not self.move_enabled:
            self.setCursor(Qt.ArrowCursor)

    def update_lyrics(self, curr: str, nxt: str) -> None:
        """현재/다음 가사 텍스트를 갱신합니다."""
        if self.curr_label.text() != curr:
            self.curr_label.setText(curr)
        if self.next_label.text() != nxt:
            self.next_label.setText(nxt)
        self.update()

    def update_song_info(self, title: str, artist: str) -> None:
        """오버레이에 제목/가수 정보를 설정합니다."""
        if title or artist:
            text = f"🎵  {title}  \u2014  {artist} 🎵" if title and artist else (title or artist)
        else:
            text = ""
        if self.song_info_label.text() != text:
            self.song_info_label.setText(text)
        self.update()

    # ------------------------------------------------------------------ #
    # 마우스 이벤트 (드래그 이동 / 리사이즈)
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event) -> None:
        if not self.move_enabled and not self.resize_enabled:
            return
        if event.button() == Qt.LeftButton:
            in_resize_corner = (
                self.resize_enabled
                and event.pos().x() > self.width() - self.resize_margin
                and event.pos().y() > self.height() - self.resize_margin
            )
            if in_resize_corner:
                self.resizing = True
            elif self.move_enabled:
                self.resizing = False
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event) -> None:
        if not self.move_enabled and not self.resize_enabled:
            return

        in_resize_corner = (
            self.resize_enabled
            and event.pos().x() > self.width() - self.resize_margin
            and event.pos().y() > self.height() - self.resize_margin
        )
        self.setCursor(Qt.SizeFDiagCursor if in_resize_corner else Qt.ArrowCursor)

        if event.buttons() == Qt.LeftButton:
            if self.resizing and self.resize_enabled:
                new_w = max(200, event.pos().x())
                new_h = max(80, event.pos().y())
                self.resize(new_w, new_h)
                self.config.update_size(new_w, new_h)
            elif not self.resizing and self.move_enabled:
                delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
                new_x = self.x() + delta.x()
                new_y = self.y() + delta.y()
                self.move(new_x, new_y)
                self.old_pos = event.globalPosition().toPoint()
                self.config.update_position(new_x, new_y)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    config = OverlayConfigManager()
    config.update_background("#000000", 150)
    config.update_text_style(color="#00FF00", outline_color="#000000", outline_width=3)
    overlay = LyricsOverlay(config)
    overlay.show()
    sys.exit(app.exec())
