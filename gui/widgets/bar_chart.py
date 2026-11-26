from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from gui import theme, typography
from gui.widgets.glass import _qcolor


class BarChartWidget(QWidget):
    """QPainter로 그리는 막대 그래프 (현재 테마 색을 따름)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels: list[str] = []
        self.data: list[int] = []
        self.setMinimumHeight(200)

    def set_data(self, labels, data, theme_mode="light"):
        # theme_mode는 예전 호출과의 호환용이며, 색은 현재 테마에서 읽습니다.
        self.labels = labels
        self.data = data
        self.update()

    def paintEvent(self, event):
        t = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w, h = self.width(), self.height()
        font = QFont(typography.family())

        if not self.data or max(self.data) == 0:
            font.setPixelSize(typography.px(14))
            painter.setFont(font)
            painter.setPen(QColor(t["text_tertiary"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "아직 이 기간의 감상 기록이 없어요")
            return

        max_val = max(self.data)
        margin_top, margin_bottom, margin_x = 34, 28, 12
        chart_h = h - margin_top - margin_bottom
        chart_w = w - margin_x * 2

        # 가로 보조선 (점선)
        grid_pen = painter.pen()
        grid_pen.setColor(_qcolor(t["hairline"]))
        grid_pen.setStyle(Qt.DashLine)
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for i in range(4):
            y = margin_top + chart_h - (i * chart_h / 3)
            painter.drawLine(margin_x, int(y), w - margin_x, int(y))

        bar_spacing = chart_w / len(self.data)
        bar_width = min(36.0, bar_spacing * 0.46)
        top_val = max_val * 1.2

        for i, (lbl, val) in enumerate(zip(self.labels, self.data)):
            cx = margin_x + i * bar_spacing + bar_spacing / 2
            bh = max((val / top_val) * chart_h, 4.0)
            bx = cx - bar_width / 2
            by = margin_top + chart_h - bh
            is_peak = val == max_val and val > 0

            # 막대: 위쪽 모서리만 둥글게, 세로 그라데이션
            r = min(8.0, bar_width / 2, bh)
            path = QPainterPath()
            path.moveTo(bx, by + bh)
            path.lineTo(bx, by + r)
            path.quadTo(bx, by, bx + r, by)
            path.lineTo(bx + bar_width - r, by)
            path.quadTo(bx + bar_width, by, bx + bar_width, by + r)
            path.lineTo(bx + bar_width, by + bh)
            path.closeSubpath()

            grad = QLinearGradient(bx, by, bx, by + bh)
            top = QColor(t["accent"])
            bottom = QColor(t["accent_2"])
            if not is_peak:
                top.setAlpha(150)
                bottom.setAlpha(90)
            grad.setColorAt(0, top)
            grad.setColorAt(1, bottom)
            painter.setPen(Qt.NoPen)
            painter.fillPath(path, grad)

            if val > 0:
                font.setPixelSize(typography.px(12))
                font.setWeight(QFont.Bold)
                painter.setFont(font)
                painter.setPen(QColor(t["accent"] if is_peak else t["text_secondary"]))
                painter.drawText(QRectF(bx - 20, by - 22, bar_width + 40, 18), Qt.AlignCenter, str(val))

            font.setPixelSize(typography.px(11))
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor(t["text_tertiary"]))
            painter.drawText(
                QRectF(cx - bar_spacing / 2, margin_top + chart_h + 8, bar_spacing, 18),
                Qt.AlignCenter, lbl,
            )
