"""공통 카드/프리셋/미리보기 위젯."""

from PySide6.QtCore import Qt, QRectF, Signal  # type: ignore
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QBrush  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QFrame,
    QGridLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui import theme, typography
from gui.widgets.glass import _qcolor
from overlay.config_manager import OverlayConfigManager
from overlay.outlined_label import OutlinedLabel


class Card(QFrame):
    """반투명 유리 카드. 색은 전역 스타일시트(QFrame#Card)에서 정합니다.

    그림자는 QGraphicsDropShadowEffect 대신 배경(GlassBackground)이 카드 뒤에 직접 그립니다.
    효과를 걸면 카드 안 버튼 하나가 다시 그려질 때 그 부분만 따로 합성돼 반투명 유리에
    사각형 경계(잔상)가 남고, 가사가 바뀔 때마다 카드 전체를 다시 그려 느려지기 때문입니다.
    """

    def __init__(self, parent=None, shadow: bool = True):
        super().__init__(parent)
        self.setObjectName("Card")
        self.casts_shadow = shadow

    def refresh_theme(self) -> None:
        """예전 호환용 (그림자 색은 배경이 테마에서 직접 읽음)."""


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
        self.setFocusPolicy(Qt.TabFocus)
        self.setAccessibleName(f"프리셋 {name}")
        self.setToolTip("클릭(또는 Enter)해서 적용" + (" · Delete 키나 × 버튼으로 삭제" if is_custom else ""))
        self._hover = False
        self.delete_btn = None
        if is_custom:
            # 우클릭만으로는 삭제 방법을 알 수 없어서, 보이는 삭제 버튼을 둡니다.
            btn = QPushButton("×", self)
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("이 프리셋 삭제")
            btn.setAccessibleName(f"{name} 프리셋 삭제")
            btn.setStyleSheet(
                "QPushButton { background: rgba(0,0,0,140); color: white; border: none;"
                " border-radius: 11px; padding: 0; font-size: 14px; font-weight: 700; }"
                "QPushButton:hover { background: #C42B30; }"
            )
            btn.move(self.width() - 26, 4)
            btn.clicked.connect(lambda: self.delete_requested.emit(self.name))
            self.delete_btn = btn

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit(self.data)
        elif event.key() == Qt.Key_Delete and self.is_custom:
            self.delete_requested.emit(self.name)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        t = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 타일
        tile = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(_qcolor(t["glass_hover"] if self._hover else t["glass_strong"]))
        active = self._hover or self.hasFocus()
        painter.setPen(QPen(QColor(t["accent"]), 2) if self.hasFocus()
                       else QPen(QColor(t["accent"]) if active else _qcolor(t["glass_border"]), 1.2))
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
        name_font = typography.font(12, QFont.DemiBold)
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


class PresetFlow(QWidget):
    """프리셋 타일을 가로 폭에 맞춰 여러 줄로 배치합니다 (창이 좁아져도 넘치지 않게)."""

    _TILE_W, _GAP = 150, 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(self._GAP)
        self._grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._items: list = []
        self._cols = 0
        # 가로 최소 폭을 열 개수에 묶지 않아야 창이 좁아질 때 열 수가 줄어듭니다.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(self._TILE_W)

    def set_items(self, items: list) -> None:
        for w in self._items:
            self._grid.removeWidget(w)
            # 이 앱은 exec() 대신 processEvents() 루프를 돌려 deleteLater가 늦을 수 있어,
            # 바로 숨기고 부모에서 떼어 화면에 남지 않게 합니다.
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._items = list(items)
        self._cols = 0
        self._relayout()

    def _relayout(self) -> None:
        cols = max(1, (self.width() + self._GAP) // (self._TILE_W + self._GAP))
        if cols == self._cols and all(self._grid.indexOf(w) >= 0 for w in self._items):
            return
        self._cols = cols
        for w in self._items:
            self._grid.removeWidget(w)
        for i, w in enumerate(self._items):
            self._grid.addWidget(w, i // cols, i % cols)
        rows = max(1, -(-len(self._items) // cols))
        self.setFixedHeight(rows * 104 + (rows - 1) * self._GAP)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()


class StylePreview(Card):
    """설정 페이지 상단의 오버레이 스타일 미리보기 카드."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(104)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("PreviewFrame")
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_text = OutlinedLabel("가사는 이렇게 보여요 (미리보기)")
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
