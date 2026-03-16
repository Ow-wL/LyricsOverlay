"""
region_selector.py
Full-screen transparent overlay that lets the user drag a rectangle
to select the lyrics region on any window.
"""

from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor


class RegionSelector(QWidget):
    """
    A full-screen, semi-transparent widget that records a drag selection.
    Emits `region_selected(QRect)` when the user releases the mouse.
    Emits `selection_cancelled()` if the user presses Escape.
    """

    region_selected = pyqtSignal(QRect)   # (left, top, width, height) in screen coords
    selection_cancelled = pyqtSignal()

    _OVERLAY_COLOR = QColor(0, 0, 0, 100)
    _SELECTION_FILL = QColor(100, 200, 255, 50)
    _SELECTION_BORDER = QColor(100, 200, 255, 220)

    def __init__(self) -> None:
        super().__init__()
        self._start: Optional[QPoint] = None
        self._end: Optional[QPoint] = None
        self._dragging = False

        self._setup_window()

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def _setup_window(self) -> None:
        # 모든 스크린을 합친 전체 영역 계산
        combined = QRect()
        for screen in QApplication.screens():
            combined = combined.united(screen.geometry())
        self.setGeometry(combined)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)   # 닫힐 때 자동 소멸
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)          # 키보드 이벤트 수신
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.globalPosition().toPoint()
            self._end = self._start
            self._dragging = True

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._end = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._end = event.globalPosition().toPoint()
            self.update()
            self._finish_selection()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.selection_cancelled.emit()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark overlay
        painter.fillRect(self.rect(), self._OVERLAY_COLOR)

        if self._start and self._end and self._start != self._end:
            sel = self._get_selection_rect()
            # Punch a lighter hole for the selection
            painter.fillRect(sel, self._SELECTION_FILL)
            pen = QPen(self._SELECTION_BORDER, 2)
            painter.setPen(pen)
            painter.drawRect(sel)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _get_selection_rect(self) -> QRect:
        return QRect(self._start, self._end).normalized()

    def _finish_selection(self) -> None:
        rect = self._get_selection_rect()
        if rect.width() > 5 and rect.height() > 5:
            self.region_selected.emit(rect)
        else:
            self.selection_cancelled.emit()
        self.close()
