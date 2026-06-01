"""가사 목록 페이지."""

from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget  # type: ignore

from gui.theme import UIConfig
from gui.widgets.card import Card


class MusicListPage(QWidget):
    """감상한 곡 목록을 보여주는 페이지."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(32)

        header = QLabel("감상 기록")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        layout.addWidget(header)
        layout.addSpacing(20)

        self.list_card = Card()
        card_layout = QVBoxLayout(self.list_card)
        self.music_list = QListWidget()
        card_layout.addWidget(self.music_list)
        layout.addWidget(self.list_card)
