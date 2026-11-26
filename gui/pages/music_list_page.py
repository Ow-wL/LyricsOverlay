"""감상 기록 페이지."""

from datetime import date, timedelta

from PySide6.QtCore import QRect, QSize, Qt, QUrl, Signal  # type: ignore
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from gui import icons
from gui import theme, typography
from gui.widgets.card import Card
from gui.widgets.glass import _qcolor, label, page_header
from lyrics.searcher import melon_song_url

_ENTRY_ROLE = Qt.UserRole + 1
_ID_ROLE = Qt.UserRole + 2  # 원본 기록 dict의 id() — 삭제할 때 원본 리스트에서 찾는 열쇠


def _format_time(ts: str) -> str:
    """'2026-11-25 14:03:10' → '2026.11.25 14:03'. 시각이 없던 옛 기록(00:00:00)은 날짜만."""
    if not isinstance(ts, str) or len(ts) < 10:
        return ""
    date = ts[:10].replace("-", ".")
    time_part = ts[11:16] if len(ts) >= 16 else ""
    if not time_part or ts[11:19] == "00:00:00":
        return date
    return f"{date}  {time_part}"


_HEADER_ROLE = Qt.UserRole + 3  # 날짜 머리 행: (제목, 곡 수 문자열)


def _day_label(day: str) -> str:
    """'2026-11-25' → '오늘' / '어제' / '11월 24일 (월)' / 올해가 아니면 '2025년 3월 2일 (일)'."""
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return day
    today = date.today()
    weekday = "월화수목금토일"[d.weekday()]
    if d == today:
        return f"오늘 · {d.month}월 {d.day}일 ({weekday})"
    if d == today - timedelta(days=1):
        return f"어제 · {d.month}월 {d.day}일 ({weekday})"
    if d.year == today.year:
        return f"{d.month}월 {d.day}일 ({weekday})"
    return f"{d.year}년 {d.month}월 {d.day}일 ({weekday})"


def _font(px: int, weight=QFont.Normal) -> QFont:
    return typography.font(px, weight)


class _HistoryDelegate(QStyledItemDelegate):
    """날짜 머리 행과 곡 행을 그립니다. 곡 행: 아이콘 · 제목(굵게)/가수 두 줄 · 시각."""

    _ROW_H = 58
    _HEAD_H = 40

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self._HEAD_H if index.data(_HEADER_ROLE) else self._ROW_H)

    def paint(self, painter, option, index) -> None:
        t = theme.active()
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        header = index.data(_HEADER_ROLE)
        if header:
            title, count = header
            r = option.rect.adjusted(14, 8, -14, 0)
            painter.setFont(_font(13, QFont.Bold))
            painter.setPen(QColor(t["text_secondary"]))
            painter.drawText(r, Qt.AlignLeft | Qt.AlignVCenter, title)
            painter.setFont(_font(12))
            painter.setPen(QColor(t["text_tertiary"]))
            painter.drawText(r, Qt.AlignRight | Qt.AlignVCenter, count)
            painter.restore()
            return

        entry = index.data(_ENTRY_ROLE) or {}
        r = option.rect.adjusted(4, 2, -4, -2)
        if option.state & QStyle.State_Selected:
            painter.setBrush(_qcolor(t["selection"]))
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(_qcolor(t["glass_hover"]))
        else:
            painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(r, 12, 12)

        # 왼쪽 아이콘 칩
        chip = QRect(r.left() + 10, r.center().y() - 18, 36, 36)
        painter.setBrush(_qcolor(t["accent_soft"]))
        painter.drawRoundedRect(chip, 10, 10)
        painter.setFont(icons.icon_font(15))
        painter.setPen(QColor(t["accent"]))
        painter.drawText(chip, Qt.AlignCenter, icons.MUSIC_NOTE)

        # 오른쪽 시각
        ts = entry.get("timestamp", "")
        time_text = "" if ts[11:19] == "00:00:00" else ts[11:16]
        time_font = _font(13, QFont.Medium)
        tw = QFontMetrics(time_font).horizontalAdvance(time_text) + 4
        painter.setFont(time_font)
        painter.setPen(QColor(t["text_secondary"]))
        painter.drawText(QRect(r.right() - 16 - tw, r.top(), tw, r.height()), Qt.AlignVCenter | Qt.AlignRight, time_text)

        # 마우스를 올리면 시각 왼쪽에 '멜론에서 열기' 아이콘 (더블 클릭 안내)
        link_w = 0
        if option.state & QStyle.State_MouseOver:
            link_w = 26
            painter.setFont(icons.icon_font(13))
            painter.setPen(QColor(t["accent"]))
            painter.drawText(QRect(r.right() - 16 - tw - 8 - link_w, r.top(), link_w, r.height()),
                             Qt.AlignCenter, icons.OPEN_LINK)

        # 제목 / 가수 두 줄
        left = chip.right() + 14
        avail = r.right() - 16 - tw - 16 - link_w - left
        title_font = _font(15, QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor(t["text_primary"]))
        painter.drawText(QRect(left, r.top() + 7, avail, 24), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(title_font).elidedText(entry.get("title", ""), Qt.ElideRight, avail))
        artist_font = _font(13)
        painter.setFont(artist_font)
        painter.setPen(QColor(t["text_secondary"]))
        painter.drawText(QRect(left, r.top() + 30, avail, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(artist_font).elidedText(entry.get("artist", ""), Qt.ElideRight, avail))
        painter.restore()


class MusicListPage(QWidget):
    """감상한 곡 목록을 최신순으로 보여주고, 제목·가수로 검색할 수 있는 페이지."""

    delete_requested = Signal(list)   # 지울 기록들의 id() 목록
    clear_requested = Signal()
    export_requested = Signal()

    def __init__(self):
        super().__init__()
        self._entries: dict[int, dict] = {}  # id() → 원본 dict (참조를 잡아 두어 id 재사용 방지)
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
        self.count_label = label("", "Secondary", "font-size: 13px; font-weight: 600;")
        top.addWidget(self.count_label)
        card_layout.addLayout(top)

        self.music_list = QListWidget()
        self.music_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.music_list.setItemDelegate(_HistoryDelegate(self.music_list))
        self.music_list.setSpacing(0)
        self.music_list.setMouseTracking(True)
        self.music_list.setSelectionMode(QListWidget.ExtendedSelection)  # Ctrl/Shift로 여러 개 선택
        self.music_list.itemSelectionChanged.connect(self._update_buttons)
        self.music_list.itemDoubleClicked.connect(self._open_in_melon)
        card_layout.addWidget(self.music_list)

        actions = QHBoxLayout()
        actions.setContentsMargins(6, 0, 6, 0)
        hint = label("더블 클릭하면 멜론에서 열려요 · Ctrl·Shift로 여러 곡 선택 · Delete 키로 삭제", "Secondary", "font-size: 12px;")
        actions.addWidget(hint)
        actions.addStretch()
        self.btn_export = QPushButton("CSV로 내보내기")
        self.btn_export.clicked.connect(self.export_requested.emit)
        self.btn_delete = QPushButton("선택 삭제")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_clear = QPushButton("전체 삭제")
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        for b in (self.btn_export, self.btn_delete, self.btn_clear):
            actions.addWidget(b)
        card_layout.addLayout(actions)

        self.empty_label = label(
            "아직 기록이 없어요. 멜론에서 음악을 재생하면 여기에 쌓입니다.", "Secondary"
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        # 목록이 숨겨졌을 때 이 문구가 남은 공간을 채워, 검색줄은 위·버튼은 아래에 붙어 있게 합니다.
        self.empty_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        card_layout.insertWidget(card_layout.indexOf(self.music_list) + 1, self.empty_label)  # 버튼 줄보다 위
        layout.addWidget(self.list_card, 1)
        self._update_count()

    # -- 데이터 --------------------------------------------------------- #

    def _make_item(self, entry: dict) -> QListWidgetItem:
        item = QListWidgetItem(f"{entry.get('title', '')} - {entry.get('artist', '')}")
        item.setData(_ENTRY_ROLE, entry)
        item.setData(_ID_ROLE, id(entry))
        self._entries[id(entry)] = entry
        item.setToolTip(f"{entry.get('title', '')} — {entry.get('artist', '')}\n{_format_time(entry.get('timestamp', ''))}\n더블 클릭하면 멜론에서 열어요")
        return item

    def _make_header(self, day: str) -> QListWidgetItem:
        item = QListWidgetItem(_day_label(day))
        item.setData(_HEADER_ROLE, (_day_label(day), ""))
        item.setData(Qt.UserRole + 4, day)
        item.setFlags(Qt.ItemIsEnabled)  # 선택·삭제 대상이 아님
        return item

    def set_history(self, history: list[dict]) -> None:
        self.music_list.clear()
        self._entries = {}
        last_day = None
        for entry in history:
            day = str(entry.get("timestamp", ""))[:10]
            if day != last_day:
                self.music_list.addItem(self._make_header(day))
                last_day = day
            self.music_list.addItem(self._make_item(entry))
        self._apply_filter(self.search.text())

    def add_entry(self, entry: dict) -> None:
        """새로 감지한 곡을 맨 위(같은 날짜 머리 아래)에 추가합니다."""
        day = str(entry.get("timestamp", ""))[:10]
        first = self.music_list.item(0)
        if first is None or first.data(Qt.UserRole + 4) != day:
            self.music_list.insertItem(0, self._make_header(day))
        item = self._make_item(entry)
        self.music_list.insertItem(1, item)
        if not self._matches(entry, self.search.text()):
            item.setHidden(True)
        self._refresh_headers()
        self._update_count()

    # -- 멜론에서 열기 ---------------------------------------------------- #

    def entry_url(self, item) -> str | None:
        if item is None or self._is_header(item):
            return None
        entry = self._entries.get(item.data(_ID_ROLE)) or item.data(_ENTRY_ROLE) or {}
        if not entry.get("title"):
            return None
        return melon_song_url(entry.get("title", ""), entry.get("artist", ""), entry.get("song_id"))

    def _open_in_melon(self, item) -> None:
        url = self.entry_url(item)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # -- 삭제 ----------------------------------------------------------- #

    def selected_ids(self) -> list[int]:
        return [it.data(_ID_ROLE) for it in self.music_list.selectedItems()
                if not it.isHidden() and it.data(_ID_ROLE) is not None]

    def _delete_selected(self) -> None:
        ids = self.selected_ids()
        if ids:
            self.delete_requested.emit(ids)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Delete and self.selected_ids():
            self._delete_selected()
            return
        super().keyPressEvent(event)

    def _update_buttons(self) -> None:
        total = len(self._entry_items())
        n = len(self.selected_ids())
        self.btn_delete.setEnabled(n > 0)
        self.btn_delete.setText(f"선택 삭제 ({n})" if n else "선택 삭제")
        self.btn_clear.setEnabled(total > 0)
        self.btn_export.setEnabled(total > 0)

    # -- 검색 ----------------------------------------------------------- #

    @staticmethod
    def _matches(entry: dict, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        return q in str(entry.get("title", "")).lower() or q in str(entry.get("artist", "")).lower()

    def _is_header(self, item) -> bool:
        return bool(item.data(_HEADER_ROLE))

    def _apply_filter(self, query: str) -> None:
        for i in range(self.music_list.count()):
            item = self.music_list.item(i)
            if not self._is_header(item):
                item.setHidden(not self._matches(item.data(_ENTRY_ROLE) or {}, query))
        self._refresh_headers()
        self._update_count()

    def _refresh_headers(self) -> None:
        """날짜 머리마다 보이는 곡 수를 적고, 보이는 곡이 없는 날짜 머리는 숨깁니다."""
        header, shown = None, 0

        def close():
            if header is not None:
                title = header.data(_HEADER_ROLE)[0]
                header.setData(_HEADER_ROLE, (title, f"{shown}곡"))
                header.setHidden(shown == 0)

        for i in range(self.music_list.count()):
            item = self.music_list.item(i)
            if self._is_header(item):
                close()
                header, shown = item, 0
            elif not item.isHidden():
                shown += 1
        close()

    def _entry_items(self):
        return [self.music_list.item(i) for i in range(self.music_list.count())
                if not self._is_header(self.music_list.item(i))]

    def _update_count(self, *args) -> None:
        entries = self._entry_items()
        total = len(entries)
        shown = sum(1 for it in entries if not it.isHidden())
        if self.search.text().strip():
            self.count_label.setText(f"검색 결과 {shown}곡 / 전체 {total}곡")
        else:
            self.count_label.setText(f"총 {total}곡" if total else "")
        self.empty_label.setVisible(total == 0)
        self.music_list.setVisible(total > 0)
        self._update_buttons()
