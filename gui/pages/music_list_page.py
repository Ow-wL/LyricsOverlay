"""감상 기록 페이지."""

from PySide6.QtCore import Qt  # type: ignore
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QVBoxLayout, QWidget  # type: ignore

from gui import icons
from gui.widgets.card import Card
from gui.widgets.glass import label, page_header


class MusicListPage(QWidget):
    """감상한 곡 목록을 보여주는 페이지."""

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
        top.addStretch()
        self.count_label = label("", "Tertiary", "font-size: 12px;")
        top.addWidget(self.count_label)
        card_layout.addLayout(top)

        self.music_list = QListWidget()
        self.music_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        card_layout.addWidget(self.music_list)
        layout.addWidget(self.list_card, 1)

        model = self.music_list.model()
        model.rowsInserted.connect(self._update_count)
        model.rowsRemoved.connect(self._update_count)

    def _update_count(self, *args) -> None:
        n = self.music_list.count()
        self.count_label.setText(f"총 {n}곡" if n else "")
