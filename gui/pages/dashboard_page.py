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

        header_layout = QHBoxLayout()
        header = QLabel("대시보드")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        header_layout.addWidget(header)
        header_layout.addStretch()

        from PySide6.QtWidgets import QPushButton
        
        view_group = QHBoxLayout()
        self.btn_session = QPushButton("세션")
        self.btn_daily = QPushButton("오늘")
        self.btn_weekly = QPushButton("이번 주")
        self.btn_monthly = QPushButton("이번 달")
        
        self.view_buttons = [self.btn_session, self.btn_daily, self.btn_weekly, self.btn_monthly]
        for btn in self.view_buttons:
            btn.setCheckable(True)
            btn.setFixedSize(80, 36)
            btn.setCursor(Qt.PointingHandCursor)
            view_group.addWidget(btn)
            
        self.btn_session.setChecked(True)
        self.current_view_mode = "session"
        
        for btn, mode in zip(self.view_buttons, ["session", "daily", "weekly", "monthly"]):
            btn.clicked.connect(lambda checked, m=mode: self.change_view(m))
            
        header_layout.addLayout(view_group)
        layout.addLayout(header_layout)

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
        s.setObjectName("StatSub")
        s.setStyleSheet(
            f"font-size: 14px; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        vbox.addWidget(t)
        vbox.addWidget(v)
        vbox.addWidget(s)
        return card

    def change_view(self, mode: str) -> None:
        self.current_view_mode = mode
        for btn, m in zip(self.view_buttons, ["session", "daily", "weekly", "monthly"]):
            btn.setChecked(m == mode)
        if hasattr(self, "latest_session_stats") and hasattr(self, "latest_play_history"):
            self.update_stats(self.latest_session_stats, self.latest_play_history)

    def update_stats(self, session_stats: dict, play_history: list[dict]) -> None:
        from datetime import datetime, timedelta
        
        self.latest_session_stats = session_stats
        self.latest_play_history = play_history

        if self.current_view_mode == "session":
            sub_text = "현재 세션 기준"
            songs = session_stats.get("play_count", 0)
            lines = session_stats.get("session_lines", 0)
            total_sec = session_stats.get("session_duration", 0)
            minutes = int(total_sec // 60)
        else:
            today = datetime.now().date()
            if self.current_view_mode == "daily":
                sub_text = "오늘 기준"
                target_dates = [today]
            elif self.current_view_mode == "weekly":
                sub_text = "이번 주 기준"
                start_of_week = today - timedelta(days=today.weekday())
                target_dates = [start_of_week + timedelta(days=i) for i in range(7)]
            else: # monthly
                sub_text = "이번 달 기준"
                target_dates = []

            songs = 0
            total_sec = 0
            lines = 0
            for entry in play_history:
                try:
                    dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").date()
                    is_in_range = False
                    if self.current_view_mode == "monthly":
                        if dt.year == today.year and dt.month == today.month:
                            is_in_range = True
                    else:
                        if dt in target_dates:
                            is_in_range = True
                            
                    if is_in_range:
                        songs += 1
                        total_sec += entry.get("play_time_sec", 0)
                        lines += entry.get("lines", 0)
                except Exception:
                    pass
            
            minutes = int(total_sec // 60)

        labels = [
            (self.stat1, f"{songs}곡", sub_text),
            (self.stat2, f"{minutes}분", sub_text),
            (self.stat3, f"{lines}줄", sub_text),
        ]
        
        for card, val, sub in labels:
            card.findChild(QLabel, "StatValue").setText(val)
            card.findChild(QLabel, "StatSub").setText(sub)
