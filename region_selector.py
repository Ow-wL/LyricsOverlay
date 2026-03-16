"""
region_selector.py
듀얼(멀티) 모니터 전체를 커버하는 드래그 영역 선택 도구.

핵심 설계:
- 각 스크린마다 개별 QWidget을 띄워 반투명 오버레이를 생성한다.
  (단일 창으로 멀티 모니터를 커버하면 DPI 스케일링/좌표 문제 발생)
- 마우스 좌표는 항상 전역(global) 좌표 기준.
- Esc 키 → 취소, 마우스 릴리즈 → region_selected emit 후 전체 닫기.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor, QScreen, QFont


# ─────────────────────────────────────────────────────────────────────────────
#  단일 스크린 오버레이 패널 (내부용)
# ─────────────────────────────────────────────────────────────────────────────

class _ScreenPanel(QWidget):
    """하나의 물리 스크린 위에 떠있는 반투명 오버레이."""

    _OVERLAY  = QColor(0, 0, 0, 110)
    _SEL_FILL = QColor(100, 210, 255, 45)
    _SEL_EDGE = QColor(100, 210, 255, 230)
    _HINT_COL = QColor(255, 255, 255, 160)

    def __init__(self, screen: QScreen, coordinator: "RegionSelector") -> None:
        super().__init__()
        self._screen      = screen
        self._coordinator = coordinator
        self._geo         = screen.geometry()   # 전역 좌표계 기준 스크린 rect

        self.setGeometry(self._geo)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)

    # ── 좌표 변환 ──────────────────────────────────────────────────────
    def _sel_in_local(self) -> Optional[QRect]:
        """전역 좌표 선택 영역을 이 스크린의 로컬 좌표로 클리핑."""
        c = self._coordinator
        if c._start is None or c._end is None:
            return None
        global_rect = QRect(c._start, c._end).normalized()
        clipped = global_rect.intersected(self._geo)
        if clipped.isEmpty():
            return None
        return clipped.translated(-self._geo.left(), -self._geo.top())

    # ── 페인트 ─────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self._OVERLAY)

        local_sel = self._sel_in_local()
        if local_sel:
            painter.fillRect(local_sel, self._SEL_FILL)
            painter.setPen(QPen(self._SEL_EDGE, 2))
            painter.drawRect(local_sel)

            # 크기 힌트 텍스트
            c = self._coordinator
            if c._start and c._end:
                r = QRect(c._start, c._end).normalized()
                hint = f"{r.width()} × {r.height()}  ({r.left()}, {r.top()})"
                painter.setPen(QPen(self._HINT_COL))
                painter.setFont(QFont("Segoe UI", 10))
                painter.drawText(local_sel.bottomLeft() + QPoint(4, 18), hint)
        else:
            painter.setPen(QPen(self._HINT_COL))
            painter.setFont(QFont("Segoe UI", 12))
            cx = self.rect().center().x()
            cy = self.rect().center().y()
            painter.drawText(cx - 200, cy, "드래그하여 가사 영역 선택   |   Esc: 취소")

    # ── 이벤트 위임 ─────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._coordinator._on_press(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:
        self._coordinator._on_move(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._coordinator._on_release(event.globalPosition().toPoint())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._coordinator._cancel()


# ─────────────────────────────────────────────────────────────────────────────
#  퍼블릭 RegionSelector
# ─────────────────────────────────────────────────────────────────────────────

class RegionSelector(QObject):
    """
    멀티 모니터 전체에 걸친 드래그 영역 선택 코디네이터.
    각 스크린에 _ScreenPanel 을 하나씩 생성해서 드래그 상태를 공유한다.
    """

    region_selected     = pyqtSignal(QRect)
    selection_cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._start:   Optional[QPoint] = None
        self._end:     Optional[QPoint] = None
        self._dragging = False
        self._panels:  list[_ScreenPanel] = []

    # ── 공개 API ────────────────────────────────────────────────────────
    def show(self) -> None:
        for screen in QApplication.screens():
            panel = _ScreenPanel(screen, self)
            self._panels.append(panel)
            panel.show()
            panel.raise_()
        if self._panels:
            self._panels[0].activateWindow()
            self._panels[0].setFocus()

    # ControlPanel 이 호출하는 메서드들과 호환
    def showFullScreen(self) -> None:
        self.show()

    def raise_(self) -> None:
        for p in self._panels:
            p.raise_()

    def activateWindow(self) -> None:
        if self._panels:
            self._panels[0].activateWindow()

    # ── 내부 이벤트 핸들러 ──────────────────────────────────────────────
    def _on_press(self, pt: QPoint) -> None:
        self._start    = pt
        self._end      = pt
        self._dragging = True
        self._repaint_all()

    def _on_move(self, pt: QPoint) -> None:
        if self._dragging:
            self._end = pt
            self._repaint_all()

    def _on_release(self, pt: QPoint) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self._end = pt
        self._repaint_all()
        self._finish()

    def _cancel(self) -> None:
        self._close_all()
        self.selection_cancelled.emit()

    # ── 헬퍼 ────────────────────────────────────────────────────────────
    def _repaint_all(self) -> None:
        for p in self._panels:
            p.update()

    def _close_all(self) -> None:
        for p in self._panels:
            p.close()
        self._panels.clear()

    def _finish(self) -> None:
        if self._start and self._end:
            rect = QRect(self._start, self._end).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self._close_all()
                self.region_selected.emit(rect)
                return
        self._cancel()
