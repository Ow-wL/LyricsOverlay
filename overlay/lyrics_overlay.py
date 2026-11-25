import sys

import win32con
import win32gui
from PySide6.QtCore import Qt, QPoint, QRect, Signal  # type: ignore
from PySide6.QtGui import QColor, QFont  # type: ignore
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget  # type: ignore

from overlay.config_manager import OverlayConfigManager
from overlay.outlined_label import OutlinedLabel
from gui.widgets.media_controls import MediaControls


class LyricsOverlay(QWidget):
    """화면 위에 항상 표시되는 가사 오버레이 창."""

    edit_finished = Signal(bool)  # 편집 모드 끝: True = 완료(적용), False = 취소

    def __init__(self, config: OverlayConfigManager | None = None):
        super().__init__()
        self.editing = False
        self.config = config if config else OverlayConfigManager()
        self.bg_color: QColor = self.config.bg_color
        # 이동·크기 조절은 '위치·크기 조정' 편집 모드에서만 켭니다.
        self.move_enabled: bool = False
        self.resize_enabled: bool = False
        self.ghost_enabled: bool = self.config.ghost_mode
        self.media_controls_enabled: bool = self.config.show_media_controls
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

        # 재생 버튼: 레이아웃 밖에 겹쳐 놓아 오버레이 크기에 영향을 주지 않습니다.
        self.media_controls = MediaControls("overlay", self)
        self.media_controls.hide()
        self._place_media_controls()

        # 편집 모드 안내와 '완료' 버튼 (평소엔 숨김)
        self.edit_hint = QLabel("드래그로 이동 · 오른쪽 아래 모서리로 크기 조절 · Enter 완료 · Esc 취소", self)
        self.edit_hint.setStyleSheet(
            "color: white; background: rgba(20, 20, 40, 200); border-radius: 8px;"
            "padding: 4px 10px; font-size: 12px; font-weight: 600;"
        )
        self.edit_hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.edit_hint.hide()
        self.edit_done_btn = QPushButton("완료", self)
        self.edit_done_btn.setCursor(Qt.PointingHandCursor)
        self.edit_done_btn.setStyleSheet(
            "QPushButton { color: white; background: #5B4BE0; border: none; border-radius: 12px;"
            " padding: 5px 16px; font-weight: 700; }"
            "QPushButton:hover { background: #4A3BCC; }"
        )
        self.edit_done_btn.clicked.connect(lambda: self.edit_finished.emit(True))
        self.edit_done_btn.hide()
        self.edit_cancel_btn = QPushButton("취소", self)
        self.edit_cancel_btn.setCursor(Qt.PointingHandCursor)
        self.edit_cancel_btn.setStyleSheet(
            "QPushButton { color: white; background: rgba(20, 20, 40, 200); border: none;"
            " border-radius: 12px; padding: 5px 14px; font-weight: 600; }"
            "QPushButton:hover { background: rgba(50, 50, 80, 220); }"
        )
        self.edit_cancel_btn.clicked.connect(lambda: self.edit_finished.emit(False))
        self.edit_cancel_btn.hide()

    # ------------------------------------------------------------------ #
    # 설정 동기화
    # ------------------------------------------------------------------ #

    def sync_with_config(self) -> None:
        """매니저의 현재 설정을 UI에 동기화합니다."""
        self.apply_settings(self.config.get_settings())

    def _update_bg_style(self) -> None:
        c = self.bg_color
        if self.editing:
            # 편집 중엔 배경이 투명해도 영역이 보이도록 점선 테두리와 최소 배경을 깝니다.
            border = "2px dashed #8B7BFF"
            alpha = max(c.alpha(), 90)
        else:
            border = f"1px solid rgba(255, 255, 255, {min(70, c.alpha() // 3 + 10)})"
            alpha = c.alpha()
        self.bg_frame.setStyleSheet(
            f"""
            QFrame#LyricsBgFrame {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, {alpha});
                border-radius: 18px;
                border: {border};
            }}
            """
        )

    def apply_settings(self, settings: dict) -> None:
        """settings dict를 받아 오버레이 외관과 동작을 갱신합니다."""
        if not settings.get("visible", True) and not self.editing:
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
        if "show_media_controls" in settings:
            self.media_controls_enabled = settings["show_media_controls"]
            if not self._media_controls_allowed():
                self.media_controls.hide()
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
        """Win32 WS_EX_TRANSPARENT으로 클릭 통과 여부를 전환합니다.

        편집 모드 중에는 설정값(enable)만 기억하고 실제로는 클릭을 받습니다.
        """
        self._ghost_pref = enable
        enable = enable and not self.editing
        self.ghost_enabled = enable
        if enable:
            self.media_controls.hide()
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

    # ------------------------------------------------------------------ #
    # 편집 모드 (위치·크기 조정)
    # ------------------------------------------------------------------ #

    def set_edit_mode(self, on: bool) -> None:
        """켜면 잠시 클릭을 받게 하고, 드래그 이동·모서리 크기 조절과 '완료/취소' 버튼을 보여 줍니다.

        저장된 설정(클릭 통과·표시)은 바꾸지 않습니다. 편집 중 프로그램이 꺼져도 원래 설정이 남습니다.
        """
        if on and not self.editing:
            self._geometry_before_edit = self.geometry()
        self.editing = on
        self.move_enabled = on
        self.resize_enabled = on
        self.set_ghost_mode(getattr(self, "_ghost_pref", self.config.ghost_mode))
        if on:
            self.media_controls.hide()
            self.show()
            self.raise_()
            # 평소엔 포커스를 뺏지 않지만, 조정 중에는 Enter/Esc를 받을 수 있게 활성화합니다.
            self.setFocusPolicy(Qt.StrongFocus)
            self.activateWindow()
            self.setFocus()
        else:
            self.setFocusPolicy(Qt.NoFocus)
            self.setCursor(Qt.ArrowCursor)
            if not self.config.visible:
                self.hide()
        self.edit_hint.setVisible(on)
        self.edit_done_btn.setVisible(on)
        self.edit_cancel_btn.setVisible(on)
        self._place_edit_widgets()
        self._update_bg_style()

    def keyPressEvent(self, event) -> None:
        if self.editing:
            if event.key() == Qt.Key_Escape:
                self.edit_finished.emit(False)
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.edit_finished.emit(True)
                return
        super().keyPressEvent(event)

    def cancel_edit_geometry(self) -> None:
        """편집을 취소하면 편집 전 위치·크기로 되돌립니다."""
        geo = getattr(self, "_geometry_before_edit", None)
        if geo is not None:
            self.setGeometry(geo)
            self.config.update_position(geo.x(), geo.y())
            self.config.update_size(geo.width(), geo.height())

    def _place_edit_widgets(self) -> None:
        if not hasattr(self, "edit_done_btn"):
            return
        self.edit_hint.adjustSize()
        self.edit_hint.move(12, 10)
        self.edit_done_btn.adjustSize()
        self.edit_done_btn.move(
            self.width() - self.edit_done_btn.width() - self.resize_margin - 8,
            self.height() - self.edit_done_btn.height() - 10,
        )
        self.edit_cancel_btn.adjustSize()
        self.edit_cancel_btn.move(
            self.edit_done_btn.x() - self.edit_cancel_btn.width() - 6, self.edit_done_btn.y()
        )
        self.edit_hint.raise_()
        self.edit_done_btn.raise_()
        self.edit_cancel_btn.raise_()

    def ensure_on_screen(self) -> bool:
        """오버레이가 어떤 모니터에도 충분히 보이지 않으면 주 모니터 아래쪽 가운데로 옮깁니다.

        옮겼으면 True.
        """
        geo = self.frameGeometry()
        for screen in QApplication.screens():
            visible = screen.availableGeometry().intersected(geo)
            if visible.width() >= min(120, geo.width()) and visible.height() >= min(40, geo.height()):
                return False
        self.reset_position()
        return True

    def reset_position(self) -> None:
        """주 모니터 아래쪽 가운데로 옮기고 저장합니다."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        w = min(self.width(), area.width() - 40)
        h = min(self.height(), area.height() - 40)
        x = area.x() + (area.width() - w) // 2
        y = area.y() + area.height() - h - int(area.height() * 0.08)
        self.setGeometry(QRect(x, y, w, h))
        self.config.update_position(x, y)
        self.config.update_size(w, h)

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
    # 재생 버튼 (마우스를 올리면 표시)
    # ------------------------------------------------------------------ #

    def _media_controls_allowed(self) -> bool:
        # 고스트 모드에서는 클릭이 통과하므로 버튼을 누를 수 없습니다.
        return self.media_controls_enabled and not self.ghost_enabled

    def _place_media_controls(self) -> None:
        mc = self.media_controls
        mc.adjustSize()
        mc.move(self.width() - mc.width() - 12, 10)
        mc.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_media_controls()
        self._place_edit_widgets()

    def enterEvent(self, event) -> None:
        if self._media_controls_allowed() and not self.editing:
            self._place_media_controls()
            self.media_controls.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.media_controls.hide()
        super().leaveEvent(event)

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
