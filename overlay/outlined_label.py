from PySide6.QtWidgets import QLabel  # type: ignore
from PySide6.QtCore import Qt  # type: ignore
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QBrush  # type: ignore


class OutlinedLabel(QLabel):
    """아웃라인(외곽선)이 있는 텍스트 레이블 위젯."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.outline_color = QColor(0, 0, 0)
        self.outline_width = 2
        self.text_color = QColor(255, 255, 255)
        self.set_style(
            QFont("Pretendard", 22), self.text_color, self.outline_color, self.outline_width
        )

    def set_style(
        self,
        font: QFont,
        text_color: QColor,
        outline_color: QColor,
        outline_width: int,
    ) -> None:
        self.setFont(font)
        self.text_color = QColor(text_color)
        self.outline_color = QColor(outline_color)
        self.outline_width = outline_width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        font_metrics = self.fontMetrics()
        text_rect = font_metrics.boundingRect(self.text())

        x = 0.0
        if self.alignment() & Qt.AlignHCenter:
            x = (self.width() - text_rect.width()) / 2
        elif self.alignment() & Qt.AlignRight:
            x = self.width() - text_rect.width()

        y = (self.height() + font_metrics.ascent() - font_metrics.descent()) / 2
        path.addText(x, y, self.font(), self.text())

        if self.outline_width > 0:
            pen = QPen(self.outline_color, self.outline_width * 2)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

        painter.fillPath(path, QBrush(self.text_color))
