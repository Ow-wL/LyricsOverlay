"""통계 페이지 및 상세 목록 다이얼로그."""

from collections import Counter
from datetime import datetime, timedelta

from gui.widgets.bar_chart import BarChartWidget

from PySide6.QtCore import Qt, QSize  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui import icons
from gui.widgets.card import Card
from gui.widgets.glass import SegmentedControl, label, page_header

# matplotlib 폰트 설정 제거됨

class DetailListDialog(QDialog):
    """전체 목록을 별도 창으로 표시하는 다이얼로그."""

    def __init__(self, title: str, items: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel(title)
        header.setStyleSheet("font-size: 20px; font-weight: 800; margin-bottom: 6px;")
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
        layout.setContentsMargins(28, 14, 28, 6)
        layout.setSpacing(20)

        # 헤더 + 뷰 모드 선택
        header_layout = QHBoxLayout()
        header_layout.addWidget(page_header("통계", "언제, 무엇을 많이 들었는지 살펴보세요"))
        header_layout.addStretch()
        self.view_control = SegmentedControl(
            [("daily", "일별"), ("weekly", "주별"), ("monthly", "월별")], self.view_mode
        )
        self.view_control.changed.connect(self.change_view)
        header_layout.addWidget(self.view_control, 0, Qt.AlignBottom)
        layout.addLayout(header_layout)

        # 그래프 카드
        self.graph_card = Card()
        graph_vbox = QVBoxLayout(self.graph_card)
        graph_vbox.setContentsMargins(24, 20, 24, 14)
        graph_vbox.setSpacing(6)
        graph_head = QHBoxLayout()
        graph_head.addWidget(label(icons.CHART, "IconGlyph", "font-size: 15px;"))
        graph_head.addSpacing(4)
        self.graph_title = label("일별 감상 기록 (최근 7일)", "CardTitle")
        graph_head.addWidget(self.graph_title)
        graph_head.addStretch()
        graph_vbox.addLayout(graph_head)
        self.bar_chart = BarChartWidget()
        graph_vbox.addWidget(self.bar_chart, 1)
        layout.addWidget(self.graph_card, 5)

        # 하단: 자주 들은 노래 / 가수
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(18)
        self.songs_card, self.top_songs_list, self.btn_more_songs = self._ranking_card(
            icons.MUSIC_NOTE, "자주 들은 노래", self._show_more_songs
        )
        self.artists_card, self.top_artists_list, self.btn_more_artists = self._ranking_card(
            icons.MUSIC, "자주 들은 가수", self._show_more_artists
        )
        bottom_layout.addWidget(self.songs_card)
        bottom_layout.addWidget(self.artists_card)
        layout.addLayout(bottom_layout, 4)

    def _ranking_card(self, glyph: str, title: str, on_more):
        card = Card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 12)
        vbox.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(label(glyph, "IconGlyph", "font-size: 15px;"))
        head.addSpacing(4)
        head.addWidget(label(title, "CardTitle"))
        head.addStretch()
        more = QPushButton("전체 보기")
        more.setObjectName("LinkButton")
        more.setCursor(Qt.PointingHandCursor)
        more.clicked.connect(on_more)
        head.addWidget(more)
        vbox.addLayout(head)
        lst = QListWidget()
        vbox.addWidget(lst)
        return card, lst, more

    # ------------------------------------------------------------------ #
    # 뷰 전환
    # ------------------------------------------------------------------ #

    def change_view(self, mode: str) -> None:
        self.view_mode = mode
        self.view_control.set_current(mode)
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
            self.bar_chart.set_data([], [], theme_mode)
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
        for rank, (song, count) in enumerate(song_counts.most_common(5), 1):
            item = QListWidgetItem(f"{rank}   {song}  ·  {count}회")
            item.setSizeHint(QSize(0, 36))
            self.top_songs_list.addItem(item)

        # TOP 5 가수
        artist_counts = Counter(
            [e["artist"] for e in play_history if e["artist"] != "Unknown"]
        )
        self.top_artists_list.clear()
        for rank, (artist, count) in enumerate(artist_counts.most_common(5), 1):
            item = QListWidgetItem(f"{rank}   {artist}  ·  {count}회")
            item.setSizeHint(QSize(0, 36))
            self.top_artists_list.addItem(item)
