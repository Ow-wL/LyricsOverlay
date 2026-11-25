from PySide6.QtWidgets import QLabel, QSizePolicy  # type: ignore
from PySide6.QtCore import Qt, QSize  # type: ignore
from PySide6.QtGui import QFont, QColor, QFontMetrics, QPainter, QPainterPath, QPen, QBrush  # type: ignore

# 글자가 넘칠 때 이 비율까지 글꼴을 줄여 보고, 그래도 넘치면 말줄임(…) 처리합니다.
_MIN_FONT_SCALE = 0.6
_MIN_POINT_SIZE = 8


class OutlinedLabel(QLabel):
    """아웃라인(외곽선)이 있는 텍스트 레이블 위젯.

    가사가 길어도 레이블(=오버레이 창)이 커지지 않도록, 너비는 레이아웃이 정하고
    텍스트를 그 너비에 맞춰 줄이거나 말줄임 처리합니다.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._style_font = QFont("Pretendard", 22)
        self.outline_color = QColor(0, 0, 0)
        self.outline_width = 2
        self.text_color = QColor(255, 255, 255)
        # 글자 아래 은은한 그림자: 밝은 배경 위에서도 또렷하고, 외곽선이 얇아도 입체감이 납니다.
        self.shadow = False
        # 글자 사이 간격(%). 작은 보조 글씨를 살짝 벌리면 깔끔해 보입니다.
        self.letter_spacing = 100.0
        # 텍스트 길이가 창 크기를 밀어내지 않도록 가로 크기 요구를 무시하게 합니다.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
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
        # 앱 스타일시트(font-family 등)가 덮어쓰지 않도록 글꼴을 따로 보관해 직접 그립니다.
        self._style_font = QFont(font)
        if self.letter_spacing != 100.0:
            self._style_font.setLetterSpacing(QFont.PercentageSpacing, self.letter_spacing)
        self.setFont(self._style_font)
        self.text_color = QColor(text_color)
        self.outline_color = QColor(outline_color)
        self.outline_width = outline_width
        self.updateGeometry()
        self.update()

    # 높이는 글꼴 기준, 너비는 요구하지 않음
    def _line_height(self) -> int:
        return QFontMetrics(self._style_font).height() + self.outline_width * 2

    def sizeHint(self) -> QSize:
        return QSize(0, self._line_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self._line_height())

    def _fitted_font_and_text(self, available: float) -> tuple[QFont, str]:
        """주어진 너비에 들어가도록 글꼴을 줄이고, 그래도 넘치면 말줄임한 텍스트를 반환."""
        text = self.text()
        font = QFont(self._style_font)
        if available <= 0 or not text:
            return font, text

        base_size = font.pointSizeF() if font.pointSizeF() > 0 else float(font.pointSize())
        width = QFontMetrics(font).horizontalAdvance(text)
        if width > available and base_size > 0:
            scaled = max(base_size * max(available / width, _MIN_FONT_SCALE), _MIN_POINT_SIZE)
            if scaled < base_size:
                font.setPointSizeF(scaled)
            width = QFontMetrics(font).horizontalAdvance(text)
        if width > available:
            text = QFontMetrics(font).elidedText(text, Qt.ElideRight, int(available))
        return font, text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        margin = self.outline_width + 4
        font, text = self._fitted_font_and_text(self.width() - margin * 2)
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(text)

        x = float(margin)
        if self.alignment() & Qt.AlignHCenter:
            x = (self.width() - text_width) / 2
        elif self.alignment() & Qt.AlignRight:
            x = self.width() - text_width - margin

        y = (self.height() + font_metrics.ascent() - font_metrics.descent()) / 2
        path = QPainterPath()
        path.addText(x, y, font, text)

        if self.shadow:
            # 아래로 살짝 내린 같은 모양을 몇 겹 겹쳐 부드러운 그림자처럼 보이게 합니다.
            for dy, alpha in ((2.2, 38), (1.4, 55), (0.8, 70)):
                painter.fillPath(path.translated(0, dy), QBrush(QColor(0, 0, 0, alpha)))
                if self.outline_width > 0:
                    painter.strokePath(path.translated(0, dy), QPen(QColor(0, 0, 0, alpha), self.outline_width * 2))

        if self.outline_width > 0:
            pen = QPen(self.outline_color, self.outline_width * 2)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

        painter.fillPath(path, QBrush(self.text_color))
