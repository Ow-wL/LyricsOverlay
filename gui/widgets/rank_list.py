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

from gui import theme, typography
from gui.widgets.artwork import paint_art
from gui.widgets.glass import _qcolor

_RANK_ROLE = Qt.UserRole + 10


def _font(px: int, weight=QFont.Normal) -> QFont:
    return typography.font(px, weight)


class RankDelegate(QStyledItemDelegate):
    ROW_H = 50

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
            painter.drawRoundedRect(QRectF(r), 8, 8)

        rank = data.get("rank", 0)
        # 순위 숫자 (상위 3위는 강조색) + 앨범 커버
        num = QRectF(r.left() + 4, r.top(), 24, r.height())
        painter.setFont(_font(15, QFont.Bold))
        painter.setPen(QColor(t["accent"] if rank <= 3 else t["text_secondary"]))
        painter.drawText(num, Qt.AlignCenter, str(rank))
        badge = QRectF(num.right() + 8, r.center().y() - 19, 38, 38)
        art = data.get("art") or {}
        paint_art(painter, badge, art.get("title") or data.get("title", ""), art.get("artist", ""),
                  art.get("song_id"), radius=5, circle=bool(art.get("circle")))

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

    def set_rows(self, rows: list[tuple]) -> None:
        """rows: [(제목, 부제, 횟수)] 또는 [(제목, 부제, 횟수, 커버 정보 dict)]"""
        self.clear()
        top = max((row[2] for row in rows), default=1)
        for rank, row in enumerate(rows, 1):
            title, subtitle, count = row[:3]
            art = row[3] if len(row) > 3 else None
            item = QListWidgetItem(f"{rank}. {title} {subtitle} {count}회")  # 접근성·복사용 텍스트
            item.setData(_RANK_ROLE, {"rank": rank, "title": title, "subtitle": subtitle,
                                      "count": count, "max": top, "art": art})
            item.setToolTip(f"{title} — {subtitle} · {count}회" if subtitle else f"{title} · {count}회")
            self.addItem(item)
