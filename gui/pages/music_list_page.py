"""감상 기록 페이지."""

from PySide6.QtCore import QRect, QSize, Qt  # type: ignore
from PySide6.QtGui import QColor, QFont, QFontMetrics  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from gui import icons
from gui import theme
from gui.widgets.card import Card
from gui.widgets.glass import _qcolor, label, page_header

_ENTRY_ROLE = Qt.UserRole + 1


def _format_time(ts: str) -> str:
    """'2026-11-25 14:03:10' → '2026.11.25 14:03'. 시각이 없던 옛 기록(00:00:00)은 날짜만."""
    if not isinstance(ts, str) or len(ts) < 10:
        return ""
    date = ts[:10].replace("-", ".")
    time_part = ts[11:16] if len(ts) >= 16 else ""
    if not time_part or ts[11:19] == "00:00:00":
        return date
    return f"{date}  {time_part}"


class _HistoryDelegate(QStyledItemDelegate):
    """한 줄에 제목(굵게) · 가수(흐리게) · 날짜(오른쪽)를 그립니다."""

    _H = 44

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self._H)

    def paint(self, painter, option, index) -> None:
        entry = index.data(_ENTRY_ROLE) or {}
        t = theme.active()
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        r = option.rect.adjusted(2, 1, -2, -1)
        if option.state & QStyle.State_Selected:
            painter.setBrush(_qcolor(t["selection"]))
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(_qcolor(t["glass_hover"]))
        else:
            painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(r, 10, 10)

        pad = 14
        when = _format_time(entry.get("timestamp", ""))
        small = QFont("Pretendard")
        small.setPixelSize(12)
        fm_small = QFontMetrics(small)
        when_w = fm_small.horizontalAdvance(when) + 4
        painter.setFont(small)
        painter.setPen(QColor(t["text_tertiary"]))
        painter.drawText(QRect(r.right() - pad - when_w, r.top(), when_w, r.height()),
                         Qt.AlignVCenter | Qt.AlignRight, when)

        avail = r.width() - pad * 2 - when_w - 16
        title_font = QFont("Pretendard")
        title_font.setPixelSize(14)
        title_font.setWeight(QFont.DemiBold)
        fm_title = QFontMetrics(title_font)
        title = fm_title.elidedText(entry.get("title", ""), Qt.ElideRight, int(avail * 0.65))
        tw = fm_title.horizontalAdvance(title)
        painter.setFont(title_font)
        painter.setPen(QColor(t["text_primary"]))
        painter.drawText(QRect(r.left() + pad, r.top(), tw + 2, r.height()), Qt.AlignVCenter, title)

        artist_font = QFont("Pretendard")
        artist_font.setPixelSize(13)
        artist = QFontMetrics(artist_font).elidedText(entry.get("artist", ""), Qt.ElideRight, max(0, avail - tw - 12))
        painter.setFont(artist_font)
        painter.setPen(QColor(t["text_secondary"]))
        painter.drawText(QRect(r.left() + pad + tw + 12, r.top(), avail - tw, r.height()), Qt.AlignVCenter, artist)
        painter.restore()


class MusicListPage(QWidget):
    """감상한 곡 목록을 최신순으로 보여주고, 제목·가수로 검색할 수 있는 페이지."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 14, 28, 6)
        layout.setSpacing(22)

        layout.addWidget(page_header("감상 기록", "지금까지 들은 곡을 최신순으로 보여줍니다"))

        self.list_card = Card()
        card_layout = QVBoxLayout(self.list_card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(6, 0, 6, 0)
        top.addWidget(label(icons.HISTORY, "IconGlyph", "font-size: 15px;"))
        top.addSpacing(4)
        top.addWidget(label("최근 재생", "CardTitle"))
        top.addSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("제목이나 가수로 검색")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("감상 기록 검색")
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)
        top.addSpacing(12)
        self.count_label = label("", "Tertiary", "font-size: 12px;")
        top.addWidget(self.count_label)
        card_layout.addLayout(top)

        self.music_list = QListWidget()
        self.music_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.music_list.setItemDelegate(_HistoryDelegate(self.music_list))
        self.music_list.setUniformItemSizes(True)
        self.music_list.setMouseTracking(True)
        card_layout.addWidget(self.music_list)

        self.empty_label = label(
            "아직 기록이 없어요. 멜론에서 음악을 재생하면 여기에 쌓입니다.", "Secondary"
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.empty_label)
        layout.addWidget(self.list_card, 1)
        self._update_count()

    # -- 데이터 --------------------------------------------------------- #

    def _make_item(self, entry: dict) -> QListWidgetItem:
        item = QListWidgetItem(f"{entry.get('title', '')} - {entry.get('artist', '')}")
        item.setData(_ENTRY_ROLE, entry)
        item.setToolTip(f"{entry.get('title', '')} — {entry.get('artist', '')}\n{_format_time(entry.get('timestamp', ''))}")
        return item

    def set_history(self, history: list[dict]) -> None:
        self.music_list.clear()
        for entry in history:
            self.music_list.addItem(self._make_item(entry))
        self._apply_filter(self.search.text())

    def add_entry(self, entry: dict) -> None:
        """새로 감지한 곡을 맨 위에 추가합니다."""
        item = self._make_item(entry)
        self.music_list.insertItem(0, item)
        if not self._matches(entry, self.search.text()):
            item.setHidden(True)
        self._update_count()

    # -- 검색 ----------------------------------------------------------- #

    @staticmethod
    def _matches(entry: dict, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        return q in str(entry.get("title", "")).lower() or q in str(entry.get("artist", "")).lower()

    def _apply_filter(self, query: str) -> None:
        for i in range(self.music_list.count()):
            item = self.music_list.item(i)
            item.setHidden(not self._matches(item.data(_ENTRY_ROLE) or {}, query))
        self._update_count()

    def _update_count(self, *args) -> None:
        total = self.music_list.count()
        shown = sum(1 for i in range(total) if not self.music_list.item(i).isHidden())
        if self.search.text().strip():
            self.count_label.setText(f"검색 결과 {shown}곡 / 전체 {total}곡")
        else:
            self.count_label.setText(f"총 {total}곡" if total else "")
        self.empty_label.setVisible(total == 0)
        self.music_list.setVisible(total > 0)
