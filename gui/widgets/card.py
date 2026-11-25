"""공통 카드/프리셋/미리보기 위젯."""

from PySide6.QtCore import Qt, QRectF, Signal  # type: ignore
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QBrush  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QFrame,
    QGraphicsDropShadowEffect,
    QVBoxLayout,
)

from gui import theme
from gui.widgets.glass import _qcolor
from overlay.config_manager import OverlayConfigManager
from overlay.outlined_label import OutlinedLabel


class Card(QFrame):
    """반투명 유리 카드. 색은 전역 스타일시트(QFrame#Card)에서 정합니다."""

    def __init__(self, parent=None, shadow: bool = True):
        super().__init__(parent)
        self.setObjectName("Card")
        self._shadow = None
        if shadow:
            self._shadow = QGraphicsDropShadowEffect(self)
            self._shadow.setBlurRadius(36)
            self._shadow.setXOffset(0)
            self._shadow.setYOffset(10)
            self.setGraphicsEffect(self._shadow)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        if self._shadow is not None:
            self._shadow.setColor(QColor(*theme.active()["shadow"]))


class PresetItem(QFrame):
    """스타일 프리셋 하나를 미리보기로 표시하는 클릭 가능한 타일."""

    clicked = Signal(dict)
    delete_requested = Signal(str)

    def __init__(self, name: str, data: dict, is_custom: bool = False, parent=None):
        super().__init__(parent)
        self.name = name
        self.data = data
        self.is_custom = is_custom
        self.setFixedSize(150, 104)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("클릭해서 적용" + (" · 우클릭으로 삭제" if is_custom else ""))
        self._hover = False

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        t = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 타일
        tile = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(_qcolor(t["glass_hover"] if self._hover else t["glass_strong"]))
        painter.setPen(QPen(QColor(t["accent"]) if self._hover else _qcolor(t["glass_border"]), 1.2))
        painter.drawRoundedRect(tile, 14, 14)

        # 오버레이 배경 미리보기
        rect = QRectF(10, 10, self.width() - 20, 54)
        bg_color = QColor(self.data.get("bg_color", "#000000"))
        bg_color.setAlpha(self.data.get("bg_alpha", 255))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 10, 10)

        # 텍스트 미리보기
        font = QFont(self.data.get("font_family", "Pretendard"))
        font.setPixelSize(15)
        font.setBold(True)
        text = "가사 미리보기"
        from PySide6.QtGui import QFontMetrics  # type: ignore
        metrics = QFontMetrics(font)
        tx = rect.center().x() - metrics.horizontalAdvance(text) / 2
        ty = rect.center().y() + (metrics.ascent() - metrics.descent()) / 2
        path = QPainterPath()
        path.addText(tx, ty, font, text)
        out_width = self.data.get("outline_width", 0)
        if out_width > 0:
            pen = QPen(QColor(self.data.get("outline_color", "#000000")), out_width)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.fillPath(path, QBrush(QColor(self.data.get("text_color", "#FFFFFF"))))

        # 이름
        name_font = QFont("Pretendard")
        name_font.setPixelSize(12)
        name_font.setWeight(QFont.DemiBold)
        painter.setFont(name_font)
        painter.setPen(QColor(t["text_secondary"]))
        painter.drawText(
            QRectF(8, 68, self.width() - 16, 30), Qt.AlignCenter,
            QFontMetrics(name_font).elidedText(self.name, Qt.ElideRight, self.width() - 16),
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.data)
        elif event.button() == Qt.RightButton and self.is_custom:
            self.delete_requested.emit(self.name)


class StylePreview(Card):
    """설정 페이지 상단의 오버레이 스타일 미리보기 카드."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(128)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("PreviewFrame")
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_text = OutlinedLabel("미리보기 가사 한 줄입니다. (Preview)")
        self.preview_text.setAlignment(Qt.AlignCenter)
        self.preview_text.setStyleSheet("background: transparent;")
        preview_layout.addWidget(self.preview_text)

        layout.addWidget(self.preview_frame)

    def update_preview(self, config: OverlayConfigManager) -> None:
        """매니저 설정을 바탕으로 미리보기 영역을 갱신합니다."""
        bg = config.bg_color
        self.preview_frame.setStyleSheet(
            f"""
            QFrame#PreviewFrame {{
                background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 40);
            }}
            """
        )
        font = QFont(config.font_family, config.font_size)
        font.setBold(True)
        self.preview_text.set_style(
            font, config.text_color, config.outline_color, config.outline_width
        )
