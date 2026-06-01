"""대시보드 페이지."""

from PySide6.QtCore import Qt  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from gui.theme import UIConfig
from gui.widgets.card import Card


class DashboardPage(QWidget):
    """실시간 가사 미리보기 및 시스템 로그를 보여주는 대시보드 페이지."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(32)

        header = QLabel("대시보드")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        layout.addWidget(header)

        # 통계 카드 3개
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        self.stat1 = self._create_stat_card("들은 노래 수", "0곡", "현재 세션 기준")
        self.stat2 = self._create_stat_card("노래 플레이 타임", "0분", "현재 세션 기준")
        self.stat3 = self._create_stat_card("매칭된 가사 라인", "0줄", "현재 세션 기준")
        stats_layout.addWidget(self.stat1)
        stats_layout.addWidget(self.stat2)
        stats_layout.addWidget(self.stat3)
        layout.addLayout(stats_layout)

        # 하단: 가사 미리보기 + 로그
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(24)

        self.lyrics_card = Card()
        lyrics_vbox = QVBoxLayout(self.lyrics_card)
        lyrics_vbox.setContentsMargins(24, 24, 24, 24)
        lyrics_title = QLabel("실시간 가사 미리보기")
        lyrics_title.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;"
        )
        self.curr_lyric = QLabel("가사를 대기 중입니다...")
        self.curr_lyric.setAlignment(Qt.AlignCenter)
        self.curr_lyric.setStyleSheet(
            "font-size: 32px; font-weight: 400; line-height: 48px;"
        )
        self.curr_lyric.setWordWrap(True)
        lyrics_vbox.addWidget(lyrics_title)
        lyrics_vbox.addStretch()
        lyrics_vbox.addWidget(self.curr_lyric)
        lyrics_vbox.addStretch()

        self.log_card = Card()
        self.log_card.setFixedWidth(400)
        log_vbox = QVBoxLayout(self.log_card)
        log_vbox.setContentsMargins(24, 24, 24, 24)
        log_title = QLabel("시스템 로그")
        log_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        self.log_list = QListWidget()
        log_vbox.addWidget(log_title)
        log_vbox.addWidget(self.log_list)

        bottom_layout.addWidget(self.lyrics_card, 2)
        bottom_layout.addWidget(self.log_card, 1)
        layout.addLayout(bottom_layout)

    def _create_stat_card(self, title: str, value: str, sub: str) -> Card:
        card = Card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(24, 24, 24, 24)
        vbox.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        v = QLabel(value)
        v.setObjectName("StatValue")
        v.setStyleSheet("font-size: 40px; font-weight: 600;")
        s = QLabel(sub)
        s.setStyleSheet(
            f"font-size: 14px; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        vbox.addWidget(t)
        vbox.addWidget(v)
        vbox.addWidget(s)
        return card
