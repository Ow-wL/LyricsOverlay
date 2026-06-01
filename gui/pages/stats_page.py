"""통계 페이지 및 상세 목록 다이얼로그."""

from collections import Counter
from datetime import datetime, timedelta

from gui.widgets.bar_chart import BarChartWidget

from PySide6.QtCore import Qt, QSize  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.theme import UIConfig
from gui.widgets.card import Card

# matplotlib 폰트 설정 제거됨

class DetailListDialog(QWidget):
    """전체 목록을 별도 창으로 표시하는 다이얼로그."""

    def __init__(self, title: str, items: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel(title)
        header.setStyleSheet("font-size: 20px; font-weight: 800; margin-bottom: 10px;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        for item_text in items:
            it = QListWidgetItem(item_text)
            it.setSizeHint(QSize(0, 40))
            self.list_widget.addItem(it)
        layout.addWidget(self.list_widget)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        if parent:
            if hasattr(parent, "centralWidget") and parent.centralWidget():
                self.setStyleSheet(parent.centralWidget().styleSheet())
            else:
                self.setStyleSheet(parent.styleSheet())
            
            # 다이얼로그 배경색이 명시적으로 적용되도록 추가 처리
            # (QSS의 QWidget 규칙이 상속되지만, 때로는 최상위 위젯 자체에는 안 먹힐 수 있음)
            self.setAttribute(Qt.WA_StyledBackground, True)


class StatsPage(QWidget):
    """음악 감상 통계 (그래프, 자주 감상한 노래/가수)를 보여주는 페이지."""

    def __init__(self):
        super().__init__()
        self.play_history: list[dict] = []
        self.theme_mode = "light"
        self.view_mode = "daily"  # "daily" | "weekly" | "monthly"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(32)

        # 헤더 + 뷰 모드 선택
        header_layout = QHBoxLayout()
        header = QLabel("음악 감상 통계")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        header_layout.addWidget(header)
        header_layout.addStretch()

        view_group = QHBoxLayout()
        view_group.setSpacing(8)
        self.btn_daily = QPushButton("일별")
        self.btn_weekly = QPushButton("주별")
        self.btn_monthly = QPushButton("월별")
        for btn in [self.btn_daily, self.btn_weekly, self.btn_monthly]:
            btn.setCheckable(True)
            btn.setFixedSize(80, 36)
            btn.setCursor(Qt.PointingHandCursor)
            view_group.addWidget(btn)
        self.btn_daily.setChecked(True)
        self.btn_daily.clicked.connect(lambda: self.change_view("daily"))
        self.btn_weekly.clicked.connect(lambda: self.change_view("weekly"))
        self.btn_monthly.clicked.connect(lambda: self.change_view("monthly"))
        header_layout.addLayout(view_group)
        layout.addLayout(header_layout)

        # 그래프 카드
        self.graph_card = Card()
        graph_vbox = QVBoxLayout(self.graph_card)
        graph_vbox.setContentsMargins(24, 24, 24, 24)
        self.graph_title = QLabel("일별 감상 기록 (최근 7일)")
        self.graph_title.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;"
        )
        graph_vbox.addWidget(self.graph_title)
        self.bar_chart = BarChartWidget()
        graph_vbox.addWidget(self.bar_chart)
        layout.addWidget(self.graph_card)

        # 하단: 자주 들은 노래 / 가수
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(24)

        self.songs_card = Card()
        songs_vbox = QVBoxLayout(self.songs_card)
        songs_vbox.setContentsMargins(20, 20, 20, 20)
        songs_header = QHBoxLayout()
        songs_title = QLabel("자주 들은 노래")
        songs_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        songs_header.addWidget(songs_title)
        songs_header.addStretch()
        self.btn_more_songs = QPushButton("자세히 보기")
        self.btn_more_songs.setFixedSize(90, 28)
        self.btn_more_songs.setStyleSheet("font-size: 12px; padding: 2px;")
        self.btn_more_songs.clicked.connect(self._show_more_songs)
        songs_header.addWidget(self.btn_more_songs)
        self.top_songs_list = QListWidget()
        songs_vbox.addLayout(songs_header)
        songs_vbox.addWidget(self.top_songs_list)

        self.artists_card = Card()
        artists_vbox = QVBoxLayout(self.artists_card)
        artists_vbox.setContentsMargins(20, 20, 20, 20)
        artists_header = QHBoxLayout()
        artists_title = QLabel("자주 들은 가수")
        artists_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        artists_header.addWidget(artists_title)
        artists_header.addStretch()
        self.btn_more_artists = QPushButton("자세히 보기")
        self.btn_more_artists.setFixedSize(90, 28)
        self.btn_more_artists.setStyleSheet("font-size: 12px; padding: 2px;")
        self.btn_more_artists.clicked.connect(self._show_more_artists)
        artists_header.addWidget(self.btn_more_artists)
        self.top_artists_list = QListWidget()
        artists_vbox.addLayout(artists_header)
        artists_vbox.addWidget(self.top_artists_list)

        bottom_layout.addWidget(self.songs_card)
        bottom_layout.addWidget(self.artists_card)
        layout.addLayout(bottom_layout)

    # ------------------------------------------------------------------ #
    # 뷰 전환
    # ------------------------------------------------------------------ #

    def change_view(self, mode: str) -> None:
        self.view_mode = mode
        self.btn_daily.setChecked(mode == "daily")
        self.btn_weekly.setChecked(mode == "weekly")
        self.btn_monthly.setChecked(mode == "monthly")
        self.update_stats(self.play_history, self.theme_mode)

    # ------------------------------------------------------------------ #
    # 상세 다이얼로그
    # ------------------------------------------------------------------ #

    def _show_more_songs(self) -> None:
        if not self.play_history:
            return
        song_counts = Counter(
            [f"{e['title']} - {e['artist']}" for e in self.play_history]
        )
        items = [f"{song} ({count}회)" for song, count in song_counts.most_common()]
        self.dialog = DetailListDialog("전체 노래 감상 순위", items, self.window())
        self.dialog.show()

    def _show_more_artists(self) -> None:
        if not self.play_history:
            return
        artist_counts = Counter(
            [e["artist"] for e in self.play_history if e["artist"] != "Unknown"]
        )
        items = [f"{artist} ({count}회)" for artist, count in artist_counts.most_common()]
        self.dialog = DetailListDialog("전체 가수 감상 순위", items, self.window())
        self.dialog.show()

    # ------------------------------------------------------------------ #
    # 통계 업데이트
    # ------------------------------------------------------------------ #

    def update_stats(self, play_history: list[dict], theme_mode: str = "light") -> None:
        """통계 데이터를 기반으로 그래프와 리스트를 업데이트합니다."""
        self.play_history = play_history
        self.theme_mode = theme_mode
        if not play_history:
            return

        today = datetime.now().date()
        counts: Counter = Counter()
        data: list[int] = []
        labels: list[str] = []

        if self.view_mode == "daily":
            self.graph_title.setText("일별 감상 기록 (최근 7일)")
            last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            for entry in play_history:
                try:
                    dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").date()
                    if dt in last_7_days:
                        counts[dt] += 1
                except Exception:
                    continue
            data = [counts.get(d, 0) for d in last_7_days]
            labels = [d.strftime("%m/%d") for d in last_7_days]

        elif self.view_mode == "weekly":
            self.graph_title.setText("주별 감상 기록 (최근 8주)")
            start_of_this_week = today - timedelta(days=today.weekday())
            weeks = [start_of_this_week - timedelta(weeks=i) for i in range(7, -1, -1)]
            for entry in play_history:
                try:
                    dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").date()
                    sow = dt - timedelta(days=dt.weekday())
                    if sow in weeks:
                        counts[sow] += 1
                except Exception:
                    continue
            data = [counts.get(w, 0) for w in weeks]
            labels = [w.strftime("%m/%d") for w in weeks]

        elif self.view_mode == "monthly":
            self.graph_title.setText("월별 감상 기록 (최근 6개월)")
            months = []
            curr = today.replace(day=1)
            for _ in range(6):
                months.insert(0, curr)
                if curr.month == 1:
                    curr = curr.replace(year=curr.year - 1, month=12)
                else:
                    curr = curr.replace(month=curr.month - 1)
            for entry in play_history:
                try:
                    dt = datetime.strptime(
                        entry["timestamp"], "%Y-%m-%d %H:%M:%S"
                    ).date().replace(day=1)
                    if dt in months:
                        counts[dt] += 1
                except Exception:
                    continue
            data = [counts.get(m, 0) for m in months]
            labels = [m.strftime("%y/%m") for m in months]

        # 네이티브 바 차트 위젯 업데이트
        self.bar_chart.set_data(labels, data, theme_mode)

        # TOP 5 노래
        song_counts = Counter(
            [f"{e['title']} - {e['artist']}" for e in play_history]
        )
        self.top_songs_list.clear()
        for song, count in song_counts.most_common(5):
            item = QListWidgetItem(f"{song} ({count}회)")
            item.setSizeHint(QSize(0, 40))
            self.top_songs_list.addItem(item)

        # TOP 5 가수
        artist_counts = Counter(
            [e["artist"] for e in play_history if e["artist"] != "Unknown"]
        )
        self.top_artists_list.clear()
        for artist, count in artist_counts.most_common(5):
            item = QListWidgetItem(f"{artist} ({count}회)")
            item.setSizeHint(QSize(0, 40))
            self.top_artists_list.addItem(item)
