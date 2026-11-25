"""대시보드 페이지."""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui import icons
from gui.widgets.card import Card
from gui.widgets.glass import SegmentedControl, ToggleSwitch, icon_chip, label, page_header
from gui.widgets.media_controls import MediaControls
from overlay.config_manager import OverlayConfigManager

_VIEW_OPTIONS = [("session", "세션"), ("daily", "오늘"), ("weekly", "이번 주"), ("monthly", "이번 달")]


class DashboardPage(QWidget):
    """지금 재생 중인 가사, 감상 요약, 오버레이 빠른 제어를 보여주는 페이지."""

    overlay_visible_toggled = Signal(bool)
    overlay_ghost_toggled = Signal(bool)
    overlay_edit_requested = Signal()
    overlay_reset_requested = Signal()

    def __init__(self, config_manager: OverlayConfigManager):
        super().__init__()
        self.config = config_manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 14, 28, 6)
        layout.setSpacing(22)

        # ── 헤더
        header_layout = QHBoxLayout()
        header_layout.addWidget(page_header("대시보드", "지금 듣고 있는 음악과 감상 기록을 한눈에 확인하세요"))
        header_layout.addStretch()
        self.current_view_mode = self.config.dashboard_view_mode
        self.view_control = SegmentedControl(_VIEW_OPTIONS, self.current_view_mode)
        self.view_control.changed.connect(self.change_view)
        header_layout.addWidget(self.view_control, 0, Qt.AlignBottom)
        layout.addLayout(header_layout)

        # ── 통계 카드 3개
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(18)
        self.stat1 = self._create_stat_card(icons.MUSIC_NOTE, "들은 노래", "0곡")
        self.stat2 = self._create_stat_card(icons.CLOCK, "감상 시간", "0분")
        self.stat3 = self._create_stat_card(icons.LINES, "매칭된 가사", "0줄")
        for card in (self.stat1, self.stat2, self.stat3):
            stats_layout.addWidget(card)
        layout.addLayout(stats_layout)

        # ── 하단: 지금 재생 중 + 로그
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(18)

        self.lyrics_card = Card()
        lyrics_vbox = QVBoxLayout(self.lyrics_card)
        lyrics_vbox.setContentsMargins(26, 22, 26, 22)
        lyrics_vbox.setSpacing(6)
        lyrics_vbox.addWidget(label("지금 재생 중", "SectionLabel"))
        self.song_title = label("재생 중인 곡이 없어요", "CardTitle", "font-size: 19px; font-weight: 800;")
        self.song_artist = label("멜론에서 음악을 재생하면 여기에 표시됩니다", "Secondary")
        # 곡 정보와 가사는 외부(창 제목·웹)에서 온 문자열이므로 HTML로 해석하지 않습니다.
        for lbl in (self.song_title, self.song_artist):
            lbl.setTextFormat(Qt.PlainText)
        lyrics_vbox.addWidget(self.song_title)
        lyrics_vbox.addWidget(self.song_artist)

        # 인식 상태 (왜 가사가 안 나오는지 바로 알 수 있게)
        self.status_title = label("준비 중", "StatusTitle")
        self.status_detail = label("", "Tertiary", "font-size: 12px;")
        self.status_detail.setWordWrap(True)
        self.status_detail.hide()
        lyrics_vbox.addSpacing(6)
        lyrics_vbox.addWidget(self.status_title)
        lyrics_vbox.addWidget(self.status_detail)

        self.curr_lyric = QLabel("가사를 기다리는 중…")
        self.curr_lyric.setTextFormat(Qt.PlainText)
        self.curr_lyric.setAlignment(Qt.AlignCenter)
        self.curr_lyric.setWordWrap(True)
        self.curr_lyric.setStyleSheet("font-size: 24px; font-weight: 700; padding: 8px 0;")
        lyrics_vbox.addStretch()
        lyrics_vbox.addWidget(self.curr_lyric)
        lyrics_vbox.addStretch()

        self.media_controls = MediaControls("app")
        lyrics_vbox.addWidget(self.media_controls, 0, Qt.AlignHCenter)

        # ── 오른쪽: 오버레이 빠른 제어 + 최근 활동
        right_col = QVBoxLayout()
        right_col.setSpacing(18)

        self.overlay_card = Card()
        oc = QVBoxLayout(self.overlay_card)
        oc.setContentsMargins(20, 18, 20, 18)
        oc.setSpacing(12)
        oc_header = QHBoxLayout()
        oc_header.addWidget(label("오버레이", "CardTitle"))
        oc_header.addStretch()
        oc_header.addWidget(label(icons.MUSIC, "IconGlyph", "font-size: 14px;"))
        oc.addLayout(oc_header)

        self.visible_switch = ToggleSwitch()
        self.visible_switch.setChecked(self.config.visible)
        self.visible_switch.toggled.connect(self.overlay_visible_toggled.emit)
        oc.addLayout(self._switch_row("화면에 표시", self.visible_switch))
        self.ghost_switch = ToggleSwitch()
        self.ghost_switch.setChecked(self.config.ghost_mode)
        self.ghost_switch.toggled.connect(self.overlay_ghost_toggled.emit)
        oc.addLayout(self._switch_row("클릭 통과 (고스트 모드)", self.ghost_switch))

        self.edit_btn = QPushButton("위치·크기 조정")
        self.edit_btn.setObjectName("PrimaryButton")
        self.edit_btn.setMinimumHeight(38)
        self.edit_btn.setToolTip("오버레이를 드래그해서 옮기고 모서리로 크기를 바꿉니다. 끝나면 오버레이의 '완료'를 누르세요.")
        self.edit_btn.clicked.connect(self.overlay_edit_requested.emit)
        oc.addWidget(self.edit_btn)
        self.reset_pos_btn = QPushButton("오버레이가 안 보여요 (위치 초기화)")
        self.reset_pos_btn.setObjectName("LinkButton")
        self.reset_pos_btn.setCursor(Qt.PointingHandCursor)
        self.reset_pos_btn.clicked.connect(self.overlay_reset_requested.emit)
        oc.addWidget(self.reset_pos_btn, 0, Qt.AlignHCenter)
        right_col.addWidget(self.overlay_card)

        self.log_card = Card()
        log_vbox = QVBoxLayout(self.log_card)
        log_vbox.setContentsMargins(20, 16, 20, 12)
        log_vbox.setSpacing(6)
        log_vbox.addWidget(label("최근 활동", "SectionLabel"))
        self.log_list = QListWidget()
        self.log_list.setObjectName("LogList")
        self.log_list.setWordWrap(True)
        self.log_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        log_vbox.addWidget(self.log_list)
        right_col.addWidget(self.log_card, 1)

        right_wrap = QWidget()
        right_wrap.setLayout(right_col)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_wrap.setFixedWidth(300)

        bottom_layout.addWidget(self.lyrics_card, 1)
        bottom_layout.addWidget(right_wrap)
        layout.addLayout(bottom_layout, 1)

    def _switch_row(self, text: str, switch) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(label(text, "", "font-weight: 600;"))
        row.addStretch()
        row.addWidget(switch)
        return row

    def sync_overlay_controls(self, editing: bool = False) -> None:
        """설정이 다른 곳(F9, 트레이, 설정 페이지)에서 바뀌어도 스위치를 맞춥니다."""
        for sw, value in ((self.visible_switch, self.config.visible),
                          (self.ghost_switch, self.config.ghost_mode)):
            sw.blockSignals(True)
            sw.setChecked(value)
            sw.blockSignals(False)
        self.edit_btn.setText("조정 완료" if editing else "위치·크기 조정")

    def _create_stat_card(self, glyph: str, title: str, value: str) -> Card:
        card = Card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(22, 18, 22, 18)
        vbox.setSpacing(2)
        top = QHBoxLayout()
        top.addWidget(label(title, "Secondary", "font-size: 13px; font-weight: 600;"))
        top.addStretch()
        top.addWidget(icon_chip(glyph, 34))
        vbox.addLayout(top)
        vbox.addWidget(label(value, "StatValue"))
        vbox.addWidget(label("현재 세션 기준", "Tertiary", "font-size: 12px;"))
        card.findChildren(QLabel)[-1].setObjectName("StatSub")
        return card

    def set_status(self, level: str, title: str, detail: str = "") -> None:
        """level: ok / warn / error. 색 점과 함께 상태를 보여 줍니다."""
        self.status_title.setProperty("level", level)
        self.status_title.setText(f"●  {title}")
        self.status_title.style().unpolish(self.status_title)
        self.status_title.style().polish(self.status_title)
        self.status_detail.setText(detail)
        self.status_detail.setVisible(bool(detail))

    def set_now_playing(self, title: str, artist: str) -> None:
        self.song_title.setText(title or "알 수 없는 곡")
        self.song_artist.setText(artist or "")

    def change_view(self, mode: str) -> None:
        self.current_view_mode = mode
        self.config.dashboard_view_mode = mode
        self.config.save_to_file()
        self.view_control.set_current(mode)
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
