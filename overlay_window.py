"""
overlay_window.py
Borderless, always-on-top, semi-transparent floating overlay.
Displays frames received from CaptureEngine.
Supports:
  - Adjustable opacity
  - Drag-to-reposition (left-click drag)
  - Resize-to-fit-content
  - Click-through mode (Win32 WS_EX_TRANSPARENT trick)
"""

from __future__ import annotations
import ctypes
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QPoint, QSize, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor
import win32gui
import win32con

# Win32 extended-window-style constants
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


class OverlayWindow(QWidget):
    """
    Floating overlay that renders captured frames.

    Parameters
    ----------
    opacity : float
        Initial window opacity [0.0 – 1.0].
    click_through : bool
        If True, mouse events pass through the overlay to whatever is below.
    """

    def __init__(self, opacity: float = 0.85, click_through: bool = False) -> None:
        super().__init__()
        self._opacity = opacity
        self._click_through = click_through
        self._drag_pos: QPoint | None = None
        self._current_pixmap: QPixmap | None = None

        self._setup_window()
        if click_through:
            self._enable_click_through()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def update_frame(self, image: QImage) -> None:
        """Slot: receive a new QImage and repaint."""
        self._current_pixmap = QPixmap.fromImage(image)
        desired = self._current_pixmap.size()
        if self.size() != desired:
            self.resize(desired)
        self.update()  # schedules a paintEvent – no blocking

    def set_opacity(self, value: float) -> None:
        """Set window opacity 0.0 (invisible) – 1.0 (opaque)."""
        self._opacity = max(0.0, min(1.0, value))
        self.setWindowOpacity(self._opacity)

    def set_click_through(self, enabled: bool) -> None:
        """Toggle click-through mode at runtime."""
        self._click_through = enabled
        if enabled:
            self._enable_click_through()
        else:
            self._disable_click_through()

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool              # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self._opacity)
        self.resize(400, 80)              # sensible default before first frame

    # ------------------------------------------------------------------ #
    #  Win32 click-through helpers                                        #
    # ------------------------------------------------------------------ #

    def _get_hwnd(self) -> int:
        return int(self.winId())

    def _enable_click_through(self) -> None:
        hwnd = self._get_hwnd()
        style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)

    def _disable_click_through(self) -> None:
        hwnd = self._get_hwnd()
        style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._current_pixmap:
            painter.drawPixmap(self.rect(), self._current_pixmap)
        else:
            # Placeholder before first frame
            painter.fillRect(self.rect(), QColor(20, 20, 20, 160))

    def mousePressEvent(self, event) -> None:
        if not self._click_through and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if not self._click_through and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
