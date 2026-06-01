"""공통 카드/프리셋/미리보기 위젯."""

from PySide6.QtCore import Qt, QRect, Signal  # type: ignore
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QFrame,
    QGraphicsDropShadowEffect,
    QVBoxLayout,
)

from gui.theme import UIConfig
from overlay.config_manager import OverlayConfigManager
from overlay.outlined_label import OutlinedLabel


class Card(QFrame):
    """그림자가 있는 기본 카드 위젯."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(*UIConfig.COLOR_SHADOW))
        self.setGraphicsEffect(shadow)


class PresetItem(QFrame):
    """스타일 프리셋 하나를 미리보기로 표시하는 클릭 가능한 프레임."""

    clicked = Signal(dict)
    delete_requested = Signal(str)

    def __init__(self, name: str, data: dict, is_custom: bool = False, parent=None):
        super().__init__(parent)
        self.name = name
        self.data = data
        self.is_custom = is_custom
        self.setFixedSize(160, 100)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("PresetItem")
        self.update_style(False)

    def update_style(self, selected: bool) -> None:
        border_color = "#7C4DFF" if selected else "#E0E0E0"
        bg_color = "#F1EBFF" if selected else "#F8F9FA"
        self.setStyleSheet(
            f"""
            QFrame#PresetItem {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
            """
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 배경 미리보기
        rect = QRect(10, 10, 140, 50)
        bg_color = QColor(self.data.get("bg_color", "#000000"))
        bg_color.setAlpha(self.data.get("bg_alpha", 255))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 8, 8)

        # 텍스트 미리보기
        font = QFont(self.data.get("font_family", "Pretendard"), 12)
        font.setBold(True)
        text = "가사 미리보기"
        path = QPainterPath()
        metrics = painter.fontMetrics()
        tx = rect.center().x() - metrics.horizontalAdvance(text) / 2
        ty = rect.center().y() + metrics.ascent() / 2 - 2
        path.addText(tx, ty, font, text)

        out_width = self.data.get("outline_width", 0)
        if out_width > 0:
            pen = QPen(QColor(self.data.get("outline_color", "#000000")), out_width)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.fillPath(path, QBrush(QColor(self.data.get("text_color", "#FFFFFF"))))

        # 이름
        painter.setPen(QColor("#555555"))
        painter.setFont(QFont("Pretendard", 9, QFont.Bold))
        painter.drawText(QRect(0, 65, 160, 30), Qt.AlignCenter, self.name)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.data)
        elif event.button() == Qt.RightButton and self.is_custom:
            self.delete_requested.emit(self.name)


class StylePreview(Card):
    """설정 페이지 상단의 오버레이 스타일 미리보기 카드."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

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
                border-radius: 12px;
                border: none;
            }}
            """
        )
        font = QFont(config.font_family, config.font_size)
        font.setBold(True)
        self.preview_text.set_style(
            font, config.text_color, config.outline_color, config.outline_width
        )
