"""가사 인식 영역 지정 대화상자.

멜론 창을 캡처한 이미지를 보여 주고, 가사(현재 줄 + 다음 줄)가 있는 곳을
마우스로 드래그해 고르게 합니다. 좌표는 캡처 이미지 픽셀 기준 [x, y, w, h]입니다.
"""

import cv2
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal  # type: ignore
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_MIN_SIZE = 10  # 이미지 픽셀 기준 최소 크기


def bgr_to_pixmap(img) -> QPixmap:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


class _RoiCanvas(QWidget):
    """캡처 이미지를 화면에 맞게 줄여 그리고, 드래그로 사각형을 고릅니다."""

    changed = Signal()

    def __init__(self, pixmap: QPixmap, roi: list[int], max_w: int = 860, max_h: int = 560):
        super().__init__()
        self._pix = pixmap
        self._scale = min(1.0, max_w / pixmap.width(), max_h / pixmap.height())
        # 작은 창은 크게 보여 줘야 고르기 쉽습니다 (최대 2배)
        if pixmap.width() * 2 <= max_w and pixmap.height() * 2 <= max_h:
            self._scale = 2.0
        self.setFixedSize(int(pixmap.width() * self._scale), int(pixmap.height() * self._scale))
        self.setCursor(Qt.CrossCursor)
        self.roi = QRect(*roi)
        self._origin: QPoint | None = None

    def _to_image(self, p: QPoint) -> QPoint:
        x = min(max(int(p.x() / self._scale), 0), self._pix.width())
        y = min(max(int(p.y() / self._scale), 0), self._pix.height())
        return QPoint(x, y)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._origin = self._to_image(event.position().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self.roi = QRect(self._origin, self._to_image(event.position().toPoint())).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._origin is not None:
            self._origin = None
            self.changed.emit()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), self._pix)
        if self.roi.width() > 0 and self.roi.height() > 0:
            s = self._scale
            r = QRectF(self.roi.x() * s, self.roi.y() * s, self.roi.width() * s, self.roi.height() * s)
            # 선택 영역 밖을 어둡게
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 110))
            full = QRectF(self.rect())
            p.drawRect(QRectF(0, 0, full.width(), r.top()))
            p.drawRect(QRectF(0, r.bottom(), full.width(), full.height() - r.bottom()))
            p.drawRect(QRectF(0, r.top(), r.left(), r.height()))
            p.drawRect(QRectF(r.right(), r.top(), full.width() - r.right(), r.height()))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#8B7BFF"), 2))
            p.drawRect(r)


class RoiSelectDialog(QDialog):
    """멜론 캡처 이미지에서 가사 영역을 고르는 대화상자. exec() 후 selected_roi를 읽습니다."""

    RESET = 2  # exec() 반환값: 기본값으로 되돌리기

    def __init__(self, image, roi: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("가사 인식 영역 지정")
        # 앱 테마는 메인 창 중앙 위젯에만 걸려 있어, 대화상자에도 같은 스타일을 입힙니다.
        main = parent.window() if parent is not None else None
        if main is not None and hasattr(main, "centralWidget") and main.centralWidget():
            self.setStyleSheet(main.centralWidget().styleSheet())
            self.setAttribute(Qt.WA_StyledBackground, True)
        self.selected_roi: list[int] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        title = QLabel("멜론 창에서 가사가 보이는 곳을 드래그해 선택하세요")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay.addWidget(title)
        hint = QLabel("현재 줄과 다음 줄이 모두 들어가게, 제목·버튼은 빠지게 잡으면 가장 잘 인식됩니다.")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.canvas = _RoiCanvas(bgr_to_pixmap(image), roi)
        lay.addWidget(self.canvas, 0, Qt.AlignCenter)

        self.size_label = QLabel()
        lay.addWidget(self.size_label)
        self.canvas.changed.connect(self._update_label)

        buttons = QHBoxLayout()
        reset = QPushButton("기본값으로")
        reset.clicked.connect(lambda: self.done(self.RESET))
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("이 영역 사용")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(reset)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_btn)
        lay.addLayout(buttons)
        self._update_label()

    def _valid(self) -> bool:
        r = self.canvas.roi
        return r.width() >= _MIN_SIZE and r.height() >= _MIN_SIZE

    def _update_label(self) -> None:
        r = self.canvas.roi
        if self._valid():
            self.size_label.setText(f"선택 영역: 위치 ({r.x()}, {r.y()}) · 크기 {r.width()} × {r.height()}")
        else:
            self.size_label.setText("영역이 너무 작아요. 가사 두 줄이 들어가게 다시 드래그하세요.")
        self.save_btn.setEnabled(self._valid())

    def _save(self) -> None:
        if self._valid():
            r = self.canvas.roi
            self.selected_roi = [r.x(), r.y(), r.width(), r.height()]
            self.accept()
