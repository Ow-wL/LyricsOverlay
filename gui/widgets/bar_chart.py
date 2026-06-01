from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import QWidget

class BarChartWidget(QWidget):
    """QPainter를 사용하여 네이티브 스타일로 렌더링되는 모던 바 차트."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self.data = []
        self.theme_mode = "light"
        self.setMinimumHeight(220)

    def set_data(self, labels, data, theme_mode="light"):
        self.labels = labels
        self.data = data
        self.theme_mode = theme_mode
        self.update()

    def paintEvent(self, event):
        if not self.labels or not self.data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()

        is_dark = self.theme_mode == "dark"
        text_color = QColor("#FFFFFF" if is_dark else "#14043F")
        grid_color = QColor("#FFFFFF" if is_dark else "#000000")
        grid_color.setAlpha(15)

        max_val = max(self.data) if self.data else 1
        if max_val == 0: max_val = 1

        # 여백 설정
        margin_bottom = 30
        margin_top = 40
        margin_left = 30
        margin_right = 30
        
        chart_h = h - margin_top - margin_bottom
        chart_w = w - margin_left - margin_right

        # 수평 그리드 그리기 (매우 연한 실선)
        pen = painter.pen()
        pen.setColor(grid_color)
        pen.setStyle(Qt.SolidLine)
        pen.setWidth(1)
        painter.setPen(pen)
        
        num_lines = 4
        for i in range(num_lines + 1):
            y = margin_top + chart_h - (i * chart_h / num_lines)
            painter.drawLine(margin_left, int(y), w - margin_right, int(y))

        # 바 그리기
        bar_count = len(self.data)
        if bar_count == 0:
            return
            
        bar_spacing = chart_w / bar_count
        # 바의 최대 너비를 제한하여 깔끔하게 보이도록 함
        bar_width = min(32.0, bar_spacing * 0.4)

        painter.setPen(Qt.NoPen)
        # 보라색 대신 시원하고 프로페셔널한 느낌의 블루 컬러 적용
        bar_color = QColor("#3B82F6")
        bar_color.setAlpha(220)
        painter.setBrush(bar_color)

        font = painter.font()
        font.setPixelSize(16)
        
        for i, (label, val) in enumerate(zip(self.labels, self.data)):
            cx = margin_left + (i * bar_spacing) + (bar_spacing / 2)
            
            # 높이 계산 (여유 공간 20% 확보)
            bh = (val / (max_val * 1.2)) * chart_h
            if bh < 2: bh = 2  # 최소 높이 보장
            
            bx = cx - (bar_width / 2)
            by = margin_top + chart_h - bh
            
            # 상단만 살짝 둥근 모서리 (반지름 4px) 적용
            radius = 2.0
            if bh < radius * 1:
                radius = bh / 1.0
                
            painter.drawRoundedRect(QRectF(bx, by, bar_width, bh), radius, radius)
            # 하단은 직각으로 덮어쓰기 (이음새가 보이지 않도록 1px 위로 겹쳐서 렌더링)
            if bh > radius:
                painter.drawRect(QRectF(bx, by + radius - 1.0, bar_width, bh - radius + 1.0))

            # 값 텍스트 (막대 위)
            if val > 0:
                painter.setPen(text_color)
                font.setWeight(QFont.Bold)
                painter.setFont(font)
                painter.drawText(
                    QRectF(bx - 20, by - 25, bar_width + 40, 20),
                    Qt.AlignCenter | Qt.AlignBottom,
                    str(val)
                )
                painter.setPen(Qt.NoPen)
                painter.setBrush(bar_color)

            # 라벨 텍스트 (X축)
            painter.setPen(text_color)
            font.setWeight(QFont.Normal)
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                QRectF(cx - bar_spacing/2, margin_top + chart_h + 10, bar_spacing, 20),
                Qt.AlignCenter | Qt.AlignTop,
                label
            )
