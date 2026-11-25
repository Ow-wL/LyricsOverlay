"""순위 목록 (자주 들은 노래·가수): 순위 배지 · 제목/부제 두 줄 · 횟수와 비율 막대."""

from PySide6.QtCore import QRect, QRectF, QSize, Qt  # type: ignore
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
)

from gui import theme
from gui.widgets.glass import _qcolor

_RANK_ROLE = Qt.UserRole + 10


def _font(px: int, weight=QFont.Normal) -> QFont:
    f = QFont("Pretendard")
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


class RankDelegate(QStyledItemDelegate):
    ROW_H = 48

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW_H)

    def paint(self, painter: QPainter, option, index) -> None:
        data = index.data(_RANK_ROLE) or {}
        t = theme.active()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r = option.rect.adjusted(2, 2, -2, -2)
        if option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(_qcolor(t["glass_hover"]))
            painter.drawRoundedRect(QRectF(r), 12, 12)

        rank = data.get("rank", 0)
        # 순위 배지: 1~3위는 채움, 나머지는 옅은 배경
        badge = QRectF(r.left() + 8, r.center().y() - 14, 28, 28)
        painter.setPen(Qt.NoPen)
        if rank <= 3:
            grad = QLinearGradient(badge.topLeft(), badge.bottomRight())
            grad.setColorAt(0, QColor(t["fill_1"]))
            grad.setColorAt(1, QColor(t["fill_2"]))
            painter.setBrush(grad)
            num_color = QColor(t["text_on_accent"])
        else:
            painter.setBrush(_qcolor(t["accent_soft"]))
            num_color = QColor(t["accent"])
        painter.drawRoundedRect(badge, 9, 9)
        painter.setFont(_font(13, QFont.Bold))
        painter.setPen(num_color)
        painter.drawText(badge, Qt.AlignCenter, str(rank))

        # 오른쪽: 횟수 + 비율 막대
        count_text = f"{data.get('count', 0)}회"
        count_font = _font(14, QFont.Bold)
        cw = QFontMetrics(count_font).horizontalAdvance(count_text)
        bar_w = 64
        right = r.right() - 10
        painter.setFont(count_font)
        painter.setPen(QColor(t["text_primary"]))
        painter.drawText(QRect(right - cw, r.top(), cw, r.height() - 12), Qt.AlignRight | Qt.AlignVCenter, count_text)
        track = QRectF(right - bar_w, r.center().y() + 9, bar_w, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(_qcolor(t["track"]))
        painter.drawRoundedRect(track, 2, 2)
        ratio = data.get("count", 0) / max(1, data.get("max", 1))
        fill = QRectF(track.left(), track.top(), max(4.0, bar_w * ratio), 4)
        grad = QLinearGradient(fill.topLeft(), fill.topRight())
        grad.setColorAt(0, QColor(t["accent"]))
        grad.setColorAt(1, QColor(t["accent_2"]))
        painter.setBrush(grad)
        painter.drawRoundedRect(fill, 2, 2)

        # 가운데: 제목(굵게) + 부제
        text_left = int(badge.right()) + 12
        text_w = int(right - bar_w - 14 - text_left)
        title = data.get("title", "")
        sub = data.get("subtitle", "")
        tf = _font(14, QFont.DemiBold)
        painter.setFont(tf)
        painter.setPen(QColor(t["text_primary"]))
        if sub:
            painter.drawText(QRect(text_left, r.top() + 6, text_w, 22), Qt.AlignLeft | Qt.AlignVCenter,
                             QFontMetrics(tf).elidedText(title, Qt.ElideRight, text_w))
            sf = _font(12)
            painter.setFont(sf)
            painter.setPen(QColor(t["text_secondary"]))
            painter.drawText(QRect(text_left, r.top() + 26, text_w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                             QFontMetrics(sf).elidedText(sub, Qt.ElideRight, text_w))
        else:
            painter.drawText(QRect(text_left, r.top(), text_w, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                             QFontMetrics(tf).elidedText(title, Qt.ElideRight, text_w))
        painter.restore()


class RankList(QListWidget):
    """순위 데이터를 [(제목, 부제, 횟수)]로 받아 그립니다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(RankDelegate(self))
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setObjectName("RankList")

    def set_rows(self, rows: list[tuple[str, str, int]]) -> None:
        self.clear()
        top = max((c for _, _, c in rows), default=1)
        for rank, (title, subtitle, count) in enumerate(rows, 1):
            item = QListWidgetItem(f"{rank}. {title} {subtitle} {count}회")  # 접근성·복사용 텍스트
            item.setData(_RANK_ROLE, {"rank": rank, "title": title, "subtitle": subtitle,
                                      "count": count, "max": top})
            item.setToolTip(f"{title} — {subtitle} · {count}회" if subtitle else f"{title} · {count}회")
            self.addItem(item)
