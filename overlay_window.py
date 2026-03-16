"""
overlay_window.py
처리된 RGBA QImage를 표시하는 보더리스 항상-위 오버레이.
배경 투명도는 TextProcessor 가 픽셀 단위로 제어하므로,
창 레벨 opacity는 전체 밝기 조절용으로만 사용한다.
"""

from __future__ import annotations
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor
import win32gui

GWL_EXSTYLE     = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED   = 0x00080000


class OverlayWindow(QWidget):
    """
    항상-위, 보더리스, 반투명 오버레이 창.
    - 드래그로 재배치 (click-through 모드 OFF 시)
    - Win32 WS_EX_TRANSPARENT 로 완전한 클릭 통과 지원
    """

    def __init__(self, opacity: float = 1.0, click_through: bool = False) -> None:
        super().__init__()
        self._opacity      = opacity
        self._click_through = click_through
        self._drag_pos: QPoint | None = None
        self._pixmap: QPixmap | None  = None

        self._setup_window()
        if click_through:
            self._enable_click_through()

    # ── 공개 API ────────────────────────────────────────────────────────
    def update_frame(self, image: QImage) -> None:
        self._pixmap = QPixmap.fromImage(image)
        if self.size() != self._pixmap.size():
            self.resize(self._pixmap.size())
        self.update()

    def set_opacity(self, value: float) -> None:
        self._opacity = max(0.05, min(1.0, value))
        self.setWindowOpacity(self._opacity)

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        if enabled:
            self._enable_click_through()
        else:
            self._disable_click_through()

    # ── 설정 ────────────────────────────────────────────────────────────
    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self._opacity)
        self.resize(400, 80)

    # ── Win32 클릭 통과 ─────────────────────────────────────────────────
    def _hwnd(self) -> int:
        return int(self.winId())

    def _enable_click_through(self) -> None:
        hwnd = self._hwnd()
        style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, GWL_EXSTYLE,
                               style | WS_EX_TRANSPARENT | WS_EX_LAYERED)

    def _disable_click_through(self) -> None:
        hwnd = self._hwnd()
        style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, GWL_EXSTYLE,
                               style & ~WS_EX_TRANSPARENT)

    # ── 이벤트 ──────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._pixmap:
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

    def mousePressEvent(self, event) -> None:
        if not self._click_through and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if not self._click_through and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_pos = None
