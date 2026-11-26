"""글래스모피즘 공통 위젯: 오로라 배경, 내비게이션 버튼, 토글 스위치, 세그먼트 컨트롤 등."""

from PySide6.QtCore import (  # type: ignore
    Property, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, Signal,
)
from PySide6.QtGui import (  # type: ignore
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (  # type: ignore
    QAbstractButton, QAbstractScrollArea, QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget,
)

from gui import theme
from gui.icons import icon_font


def draw_focus_ring(p: QPainter, rect: QRectF, radius: float) -> None:
    """키보드로 포커스가 왔을 때 보이는 테두리 (마우스 사용자에겐 보이지 않음)."""
    pen = QPen(QColor(theme.active()["accent"]), 2)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)


class KeyboardFocusMixin:
    """Tab 키로 포커스가 왔을 때만 포커스 링을 그리기 위한 상태 추적."""

    _kbd_focus = False

    def focusInEvent(self, event) -> None:
        self._kbd_focus = event.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        self._kbd_focus = False
        super().focusOutEvent(event)
        self.update()


def _qcolor(css: str) -> QColor:
    """'rgba(r, g, b, a)' 또는 '#hex' 문자열을 QColor로 변환."""
    css = css.strip()
    if css.startswith("rgba("):
        r, g, b, a = (int(float(v)) for v in css[5:-1].split(","))
        return QColor(r, g, b, a)
    return QColor(css)


# ------------------------------------------------------------------ #
# 배경
# ------------------------------------------------------------------ #

class GlassBackground(QWidget):
    """그라데이션 위에 큰 색 번짐을 그려, 유리 패널이 비쳐 보일 배경을 만듭니다."""

    def paintEvent(self, event) -> None:
        t = theme.active()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0, QColor(t["bg_top"]))
        base.setColorAt(1, QColor(t["bg_bottom"]))
        p.fillRect(self.rect(), base)

        size = max(w, h)
        for fx, fy, fr, color, alpha in t["blobs"]:
            center = QPointF(w * fx, h * fy)
            radius = size * fr
            grad = QRadialGradient(center, radius)
            c = QColor(color)
            c.setAlphaF(alpha)
            grad.setColorAt(0.0, c)
            c2 = QColor(color)
            c2.setAlphaF(alpha * 0.35)
            grad.setColorAt(0.45, c2)
            c3 = QColor(color)
            c3.setAlphaF(0.0)
            grad.setColorAt(1.0, c3)
            p.fillRect(self.rect(), QBrush(grad))

        self._paint_card_shadows(p, t)

    # 카드 그림자: 같은 위치에 늘 같은 픽셀을 그리므로, 일부만 다시 그려도 경계가 생기지 않습니다.
    _SHADOW_STEPS = ((14, 0.10), (10, 0.16), (7, 0.22), (4, 0.24), (2, 0.28))

    def _paint_card_shadows(self, p: QPainter, t: dict) -> None:
        r, g, b, a = t["shadow"]
        p.setPen(Qt.NoPen)
        for card in self.findChildren(QFrame):
            if not getattr(card, "casts_shadow", False) or not card.isVisible():
                continue
            rect = QRectF(QRect(card.mapTo(self, QPoint(0, 0)), card.size()))
            clip = self._visible_area(card)
            if clip is None:
                continue
            radius = 22 if card.objectName() == "Sidebar" else 20
            # 카드 안쪽은 비워 둡니다 (반투명 유리 밑에 그림자가 비치면 카드가 탁해 보임)
            outside = QPainterPath()
            outside.addRect(clip)
            inner = QPainterPath()
            inner.addRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
            p.save()
            p.setClipPath(outside.subtracted(inner))
            for spread, weight in self._SHADOW_STEPS:
                p.setBrush(QColor(r, g, b, int(a * weight)))
                p.drawRoundedRect(rect.adjusted(-spread * 0.6, -spread * 0.2 + 6, spread * 0.6, spread + 4),
                                  radius + spread * 0.5, radius + spread * 0.5)
            p.restore()

    def _visible_area(self, card: QWidget):
        """카드가 스크롤 영역 안에 있으면 그 보이는 부분까지만 그림자를 그립니다."""
        area = QRectF(self.rect())
        w = card.parentWidget()
        while w is not None and w is not self:
            if isinstance(w, QAbstractScrollArea):
                vp = w.viewport()
                area = area.intersected(QRectF(QRect(vp.mapTo(self, QPoint(0, 0)), vp.size())))
            w = w.parentWidget()
        return None if area.isEmpty() else area


# ------------------------------------------------------------------ #
# 내비게이션 버튼 (아이콘 + 글자, 선택 시 강조 배경)
# ------------------------------------------------------------------ #

class NavButton(KeyboardFocusMixin, QAbstractButton):
    def __init__(self, glyph: str, text: str, height: int = 44, parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(height)
        self.setFocusPolicy(Qt.TabFocus)  # 키보드로 Tab 이동 → Space로 선택
        self.setAccessibleName(text)
        self._hover = False

    def sizeHint(self) -> QSize:
        return QSize(160, self.height())

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        t = theme.active()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if self.isChecked():
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, QColor(t["fill_1"]))
            grad.setColorAt(1, QColor(t["fill_2"]))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 12, 12)
            fg = QColor(t["text_on_accent"])
        else:
            if self._hover:
                p.setBrush(_qcolor(t["glass_hover"]))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(rect, 12, 12)
            fg = QColor(t["text_primary"] if self._hover else t["text_secondary"])

        p.setPen(fg)
        p.setFont(icon_font(16))
        p.drawText(QRectF(14, 0, 22, self.height()), Qt.AlignVCenter | Qt.AlignHCenter, self.glyph)

        font = QFont(self.font())
        font.setFamily("Pretendard")
        font.setPixelSize(14)
        font.setWeight(QFont.Bold if self.isChecked() else QFont.DemiBold)
        p.setFont(font)
        p.drawText(QRectF(46, 0, self.width() - 50, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        if self.hasFocus() and self._kbd_focus:
            draw_focus_ring(p, rect, 12)


# ------------------------------------------------------------------ #
# 토글 스위치 (QCheckBox와 같은 신호/메서드)
# ------------------------------------------------------------------ #

class ToggleSwitch(KeyboardFocusMixin, QCheckBox):
    _W, _H = 44, 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self._W + 4, self._H + 4)  # 포커스 링 자리
        self.setFocusPolicy(Qt.TabFocus)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def setChecked(self, checked: bool) -> None:  # 애니메이션 없이 바로 반영
        super().setChecked(checked)
        self._anim.stop()
        self._offset = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def sizeHint(self) -> QSize:
        return QSize(self._W + 4, self._H + 4)

    def paintEvent(self, event) -> None:
        t = theme.active()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.hasFocus() and self._kbd_focus:
            draw_focus_ring(p, QRectF(self.rect()), (self._H + 4) / 2)
        p.translate(2, 2)
        track = QRectF(0.5, 0.5, self._W - 1, self._H - 1)

        off_color = _qcolor(t["track"])
        on_grad = QLinearGradient(track.topLeft(), track.topRight())
        on_grad.setColorAt(0, QColor(t["accent"]))
        on_grad.setColorAt(1, QColor(t["accent_2"]))

        p.setPen(Qt.NoPen)
        p.setBrush(off_color)
        p.drawRoundedRect(track, self._H / 2, self._H / 2)
        if self._offset > 0:
            p.setOpacity(self._offset)
            p.setBrush(on_grad)
            p.drawRoundedRect(track, self._H / 2, self._H / 2)
            p.setOpacity(1.0)

        d = self._H - 6
        x = 3 + (self._W - d - 6) * self._offset
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, 4, d, d))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 3, d, d))


# ------------------------------------------------------------------ #
# 작은 도우미들
# ------------------------------------------------------------------ #

def icon_chip(glyph: str, size: int = 36) -> QLabel:
    """둥근 강조 배경 위 아이콘 (통계 카드 등)."""
    lbl = QLabel(glyph)
    lbl.setObjectName("IconChip")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedSize(size, size)
    return lbl


def label(text: str, object_name: str = "", style: str = "") -> QLabel:
    lbl = QLabel(text)
    if object_name:
        lbl.setObjectName(object_name)
    if style:
        lbl.setStyleSheet(style)
    return lbl


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def page_header(title: str, subtitle: str = "") -> QWidget:
    """페이지 제목 + 부제목."""
    w = QWidget()
    from PySide6.QtWidgets import QVBoxLayout  # type: ignore
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(label(title, "PageHeader"))
    if subtitle:
        lay.addWidget(label(subtitle, "PageSubtitle"))
    return w


class SegmentedControl(QFrame):
    """여러 선택지 중 하나를 고르는 알약 모양 버튼 묶음."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], current: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SegmentGroup")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self.buttons: dict[str, QPushButton] = {}
        for key, text in options:
            btn = QPushButton(text)
            btn.setObjectName("Segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.TabFocus)
            btn.clicked.connect(lambda _=False, k=key: self._select(k, emit=True))
            lay.addWidget(btn)
            self.buttons[key] = btn
        self._select(current, emit=False)

    def _select(self, key: str, emit: bool) -> None:
        for k, b in self.buttons.items():
            b.setChecked(k == key)
        if emit:
            self.changed.emit(key)

    def set_current(self, key: str) -> None:
        self._select(key, emit=False)
