import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QFrame, QListWidget, QSlider, QCheckBox, QGroupBox,
                             QListWidgetItem, QGraphicsDropShadowEffect, QScrollArea,
                             QColorDialog, QFontDialog, QLineEdit, QGridLayout)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QRect, Signal
from PySide6.QtGui import QIcon, QColor, QFont, QPixmap, QFontDatabase, QKeyEvent, QKeySequence, QPainter, QBrush, QPen, QPainterPath, QFontMetrics
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from collections import Counter
from datetime import datetime, timedelta

# Matplotlib 한글 폰트 설정
try:
    # 시스템에서 한글 폰트 찾기
    import matplotlib.font_manager as fm
    font_list = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    korean_font = None
    
    # 우선순위: 맑은 고딕, 나눔고딕, 본고딕 등
    target_fonts = ['Malgun Gothic', 'NanumGothic', 'AppleGothic', 'Noto Sans CJK KR', 'Gulim', 'Batang']
    
    for target in target_fonts:
        for fpath in font_list:
            if target.lower() in fpath.lower():
                korean_font = target
                break
        if korean_font:
            break
            
    if korean_font:
        plt.rcParams['font.family'] = korean_font
    else:
        # 못 찾으면 기본 맑은 고딕 시도
        plt.rcParams['font.family'] = 'Malgun Gothic'
    
    plt.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"Matplotlib font error: {e}")
    pass

# Set up path for independent execution
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.roi_selector import ROISelector
from lyrics_overlay import LyricsOverlay, OverlayConfigManager

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(*UIConfig.COLOR_SHADOW))
        self.setGraphicsEffect(shadow)

class PresetItem(QFrame):
    clicked = Signal(dict)
    delete_requested = Signal(str)

    def __init__(self, name, data, is_custom=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.data = data
        self.is_custom = is_custom
        self.setFixedSize(160, 100)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("PresetItem")
        self.update_style(False)

    def update_style(self, selected):
        border_color = "#7C4DFF" if selected else "#E0E0E0"
        bg_color = "#F8F9FA" if not selected else "#F1EBFF"
        self.setStyleSheet(f"""
            QFrame#PresetItem {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw Preview Background
        rect = QRect(10, 10, 140, 50)
        bg_color = QColor(self.data.get("bg_color", "#000000"))
        bg_color.setAlpha(self.data.get("bg_alpha", 255))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 8, 8)
        
        # Draw Preview Text with Outline
        font = QFont(self.data.get("font_family", "Pretendard"), 12)
        font.setBold(True)
        text = "가사 미리보기"
        
        path = QPainterPath()
        metrics = painter.fontMetrics()
        tx = rect.center().x() - metrics.horizontalAdvance(text) / 2
        ty = rect.center().y() + metrics.ascent() / 2 - 2
        path.addText(tx, ty, font, text)
        
        # Outline
        out_width = self.data.get("outline_width", 0)
        if out_width > 0:
            pen = QPen(QColor(self.data.get("outline_color", "#000000")), out_width)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
            
        # Text fill
        painter.fillPath(path, QBrush(QColor(self.data.get("text_color", "#FFFFFF"))))
        
        # Draw Name
        painter.setPen(QColor("#555555"))
        painter.setFont(QFont("Pretendard", 9, QFont.Bold))
        name_rect = QRect(0, 65, 160, 30)
        painter.drawText(name_rect, Qt.AlignCenter, self.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.data)
        elif event.button() == Qt.RightButton and self.is_custom:
            self.delete_requested.emit(self.name)

class StylePreview(Card):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("PreviewFrame")
        self.preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_text = QLabel("미리보기 가사 한 줄입니다. (Preview)")
        self.preview_text.setAlignment(Qt.AlignCenter)
        self.preview_text.setStyleSheet("background: transparent;")
        self.preview_layout.addWidget(self.preview_text)
        
        self.layout.addWidget(self.preview_frame)
        
        self.config_data = {}

    def update_preview(self, config):
        self.config_data = {
            "bg_color": config.bg_color,
            "text_color": config.text_color,
            "outline_color": config.outline_color,
            "outline_width": config.outline_width,
            "font_family": config.font_family,
            "font_size": config.font_size
        }
        
        # Update Background
        bg = self.config_data["bg_color"]
        self.preview_frame.setStyleSheet(f"""
            QFrame#PreviewFrame {{
                background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                border-radius: 12px;
            }}
        """)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.config_data: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # We draw the text manually to handle the outline correctly
        rect = self.preview_frame.geometry()
        # Offset for card contents margins
        rect.translate(self.layout.contentsMargins().left(), self.layout.contentsMargins().top())
        
        font = QFont(self.config_data["font_family"], 22)
        font.setBold(True)
        text = self.preview_text.text()
        
        path = QPainterPath()
        metrics = QFontMetrics(font)
        tx = rect.center().x() - metrics.horizontalAdvance(text) / 2
        ty = rect.center().y() + metrics.ascent() / 2 - 2
        path.addText(tx, ty, font, text)
        
        # Outline
        out_width = self.config_data["outline_width"]
        if out_width > 0:
            pen = QPen(self.config_data["outline_color"], out_width * 1.5)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
            
        # Text fill
        painter.fillPath(path, QBrush(self.config_data["text_color"]))

################################################################################
# UI CONFIGURATION
################################################################################
# ... (UIConfig and Theme classes remain the same)
class UIConfig:
    # ----- Sidebar Icons -----
    ICON_COLOR_DASHBOARD = "#F17979"
    ICON_COLOR_MUSIC = "#7EEFA4"
    ICON_COLOR_STATS = "#FFB74D"
    ICON_COLOR_SETTINGS = "#75EDF1"

    # ----- Common Styles -----
    COLOR_SECONDARY_TEXT = "#828282"
    COLOR_SHADOW = (0, 0, 0, 20)  # RGBA tuple
    
    # ----- Light Theme -----
    LIGHT_BG_MAIN = "#FFFFFF"
    LIGHT_BG_SIDEBAR = "#F8F9FA"
    LIGHT_BG_CARD = "#FFFFFF"
    LIGHT_BORDER = "#E0E0E0"
    LIGHT_TEXT_PRIMARY = "#14043F"
    LIGHT_TEXT_SECONDARY = "#555555"
    LIGHT_ACCENT = "#14043F"
    LIGHT_ACCENT_HOVER = "#2A1066"
    
    LIGHT_SB_NORMAL_TEXT = "#495057"
    LIGHT_SB_ACTIVE_BG = "#E9ECEF"
    LIGHT_SB_ACTIVE_TEXT = "#14043F"
    LIGHT_SB_HOVER_BG = "#F1F3F5"
    LIGHT_BTN_BG = "#FFFFFF"
    LIGHT_BTN_TEXT = "#14043F"
    LIGHT_BTN_BORDER = "#DEE2E6"
    
    # [리스트 아이템] 선택 색상 - 라이트 모드
    LIGHT_LIST_SEL_BG = "#E9ECEF"
    LIGHT_LIST_SEL_TEXT = "#4400FF"
    
    # [글꼴 변경] 버튼 - 라이트 모드
    LIGHT_FONT_BTN_BG = "#7C4DFF"
    LIGHT_FONT_BTN_TEXT = "#14043F"

    # ----- Dark Theme -----
    DARK_BG_MAIN = "#121212"
    DARK_BG_SIDEBAR = "#1E1E1E"
    DARK_BG_CARD = "#121212"
    DARK_BORDER = "#333333"
    DARK_TEXT_PRIMARY = "#FFFFFF"
    DARK_TEXT_SECONDARY = "#AAAAAA"
    DARK_ACCENT = "#7C4DFF"
    DARK_ACCENT_HOVER = "#9E7BFF"
    
    DARK_SB_NORMAL_TEXT = "#ADB5BD"
    DARK_SB_ACTIVE_BG = "#2C2C2C"
    DARK_SB_ACTIVE_TEXT = "#FFFFFF"
    DARK_SB_HOVER_BG = "#1A1A1A"
    DARK_BTN_BG = "#2C2C2C"
    DARK_BTN_TEXT = "#FFFFFF"
    DARK_BTN_BORDER = "#444444"

    # [리스트 아이템] 선택 색상 - 다크 모드
    DARK_LIST_SEL_BG = "#333333"
    DARK_LIST_SEL_TEXT = "#FFFFFF"

    # [글꼴 변경] 버튼 - 다크 모드
    DARK_FONT_BTN_BG = "#7C4DFF"
    DARK_FONT_BTN_TEXT = "#FFFFFF"

    # ----- Font Sizes -----
    FS_HEADER_MAIN = "36px"
    FS_SIDEBAR_TITLE = "26px"
    FS_TITLE_L = "22px"
    FS_TITLE_M = "20px"
    FS_TITLE_S = "18px"
    FS_DESC = "15px"
    FS_BODY = "16px"
    FS_LIST = "15px"
    FS_BUTTON = "14px"
    FS_THEME_BUTTON = "15px"
    FS_SIDEBAR_BTN = "17px"
    FS_CHECKBOX = "15px"

################################################################################

class Theme:
    LIGHT = {
        "bg_main": UIConfig.LIGHT_BG_MAIN,
        "bg_sidebar": UIConfig.LIGHT_BG_SIDEBAR,
        "bg_card": UIConfig.LIGHT_BG_CARD,
        "border": UIConfig.LIGHT_BORDER,
        "text_primary": UIConfig.LIGHT_TEXT_PRIMARY,
        "text_secondary": UIConfig.LIGHT_TEXT_SECONDARY,
        "accent": UIConfig.LIGHT_ACCENT,
        "accent_hover": UIConfig.LIGHT_ACCENT_HOVER,
        "sb_normal_text": UIConfig.LIGHT_SB_NORMAL_TEXT,
        "sb_active_bg": UIConfig.LIGHT_SB_ACTIVE_BG,
        "sb_active_text": UIConfig.LIGHT_SB_ACTIVE_TEXT,
        "sb_hover_bg": UIConfig.LIGHT_SB_HOVER_BG,
        "btn_bg": UIConfig.LIGHT_BTN_BG,
        "btn_text": UIConfig.LIGHT_BTN_TEXT,
        "btn_border": UIConfig.LIGHT_BTN_BORDER,
        "btn_font_bg": UIConfig.LIGHT_FONT_BTN_BG,
        "btn_font_text": UIConfig.LIGHT_FONT_BTN_TEXT,
        "list_sel_bg": UIConfig.LIGHT_LIST_SEL_BG,
        "list_sel_text": UIConfig.LIGHT_LIST_SEL_TEXT
    }
    DARK = {
        "bg_main": UIConfig.DARK_BG_MAIN,
        "bg_sidebar": UIConfig.DARK_BG_SIDEBAR,
        "bg_card": UIConfig.DARK_BG_CARD,
        "border": UIConfig.DARK_BORDER,
        "text_primary": UIConfig.DARK_TEXT_PRIMARY,
        "text_secondary": UIConfig.DARK_TEXT_SECONDARY,
        "accent": UIConfig.DARK_ACCENT,
        "accent_hover": UIConfig.DARK_ACCENT_HOVER,
        "sb_normal_text": UIConfig.DARK_SB_NORMAL_TEXT,
        "sb_active_bg": UIConfig.DARK_SB_ACTIVE_BG,
        "sb_active_text": UIConfig.DARK_SB_ACTIVE_TEXT,
        "sb_hover_bg": UIConfig.DARK_SB_HOVER_BG,
        "btn_bg": UIConfig.DARK_BTN_BG,
        "btn_text": UIConfig.DARK_BTN_TEXT,
        "btn_border": UIConfig.DARK_BTN_BORDER,
        "btn_font_bg": UIConfig.DARK_FONT_BTN_BG,
        "btn_font_text": UIConfig.DARK_FONT_BTN_TEXT,
        "list_sel_bg": UIConfig.DARK_LIST_SEL_BG,
        "list_sel_text": UIConfig.DARK_LIST_SEL_TEXT
    }

class ThemeManager:
    def __init__(self):
        self.current_theme = Theme.LIGHT

    def toggle_theme(self):
        self.current_theme = Theme.DARK if self.current_theme == Theme.LIGHT else Theme.LIGHT
        return self.current_theme

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(*UIConfig.COLOR_SHADOW))
        self.setGraphicsEffect(shadow)

class SidebarButton(QPushButton):
    def __init__(self, text, icon_color="#000000", parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(55)
        self.setCursor(Qt.PointingHandCursor)
        
        self.icon_circle = QFrame(self)
        self.icon_circle.setFixedSize(16, 16)
        self.icon_circle.setStyleSheet(f"background-color: {icon_color}; border-radius: 8px; border: none;")
        self.icon_circle.move(20, 19)
        self.icon_circle.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.setContentsMargins(50, 0, 0, 0)

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(32)

        header = QLabel("대시보드")
        header.setObjectName("PageHeader")
        header.setStyleSheet(f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;")
        self.layout.addWidget(header)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        
        self.stat1 = self.create_stat_card("들은 노래 수", "0곡", "현재 세션 기준")
        self.stat2 = self.create_stat_card("노래 플레이 타임", "0분", "현재 세션 기준")
        self.stat3 = self.create_stat_card("매칭된 가사 라인", "0줄", "현재 세션 기준")
        
        stats_layout.addWidget(self.stat1)
        stats_layout.addWidget(self.stat2)
        stats_layout.addWidget(self.stat3)
        self.layout.addLayout(stats_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(24)

        self.lyrics_card = Card()
        lyrics_vbox = QVBoxLayout(self.lyrics_card)
        lyrics_vbox.setContentsMargins(24, 24, 24, 24)
        
        lyrics_title = QLabel("실시간 가사 미리보기")
        lyrics_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        
        self.curr_lyric = QLabel("가사를 대기 중입니다...")
        self.curr_lyric.setAlignment(Qt.AlignCenter)
        self.curr_lyric.setStyleSheet("font-size: 32px; font-weight: 400; line-height: 48px;")
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
        self.layout.addLayout(bottom_layout)

    def create_stat_card(self, title, value, sub):
        card = Card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(24, 24, 24, 24)
        vbox.setSpacing(8)
        
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        v = QLabel(value)
        v.setObjectName("StatValue")
        v.setStyleSheet("font-size: 40px; font-weight: 600;")
        s = QLabel(sub)
        s.setStyleSheet(f"font-size: 14px; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        
        vbox.addWidget(t)
        vbox.addWidget(v)
        vbox.addWidget(s)
        return card

class MusicListPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        header = QLabel("가사 목록")
        header.setObjectName("PageHeader")
        header.setStyleSheet(f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;")
        layout.addWidget(header)
        layout.addSpacing(20)
        
        self.list_card = Card()
        card_layout = QVBoxLayout(self.list_card)
        
        self.music_list = QListWidget()
        
        card_layout.addWidget(self.music_list)
        layout.addWidget(self.list_card)

class DetailListDialog(QWidget):
    def __init__(self, title, items, parent=None):
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
        
        # 테마 적용 (부모 윈도우 스타일 상속)
        if parent:
            self.setStyleSheet(parent.styleSheet())

class StatsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.play_history = []
        self.theme_mode = "light"
        self.view_mode = "daily" # "daily", "weekly", "monthly"

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(24)

        header_layout = QHBoxLayout()
        header = QLabel("음악 감상 통계")
        header.setObjectName("PageHeader")
        header.setStyleSheet(f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        # View Mode Selector
        self.view_group = QHBoxLayout()
        self.btn_daily = QPushButton("일별")
        self.btn_weekly = QPushButton("주별")
        self.btn_monthly = QPushButton("월별")
        
        for btn in [self.btn_daily, self.btn_weekly, self.btn_monthly]:
            btn.setCheckable(True)
            btn.setFixedSize(80, 36)
            btn.setCursor(Qt.PointingHandCursor)
            self.view_group.addWidget(btn)
            
        self.btn_daily.setChecked(True)
        self.btn_daily.clicked.connect(lambda: self.change_view("daily"))
        self.btn_weekly.clicked.connect(lambda: self.change_view("weekly"))
        self.btn_monthly.clicked.connect(lambda: self.change_view("monthly"))
        
        header_layout.addLayout(self.view_group)
        self.layout.addLayout(header_layout)

        # Graph Card
        self.graph_card = Card()
        graph_vbox = QVBoxLayout(self.graph_card)
        graph_vbox.setContentsMargins(24, 24, 24, 24)
        
        self.graph_title = QLabel("일별 감상 기록 (최근 7일)")
        self.graph_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        graph_vbox.addWidget(self.graph_title)

        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        graph_vbox.addWidget(self.canvas)
        
        self.layout.addWidget(self.graph_card)

        # Bottom Stats (Top Songs / Top Artists)
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(24)

        # Top Songs Card
        self.songs_card = Card()
        songs_vbox = QVBoxLayout(self.songs_card)
        songs_vbox.setContentsMargins(20, 20, 20, 20)
        
        songs_header = QHBoxLayout()
        songs_title = QLabel("가장 많이 들은 노래 TOP 5")
        songs_title.setStyleSheet(f"font-size: 16px; font-weight: 700;")
        songs_header.addWidget(songs_title)
        songs_header.addStretch()
        
        self.btn_more_songs = QPushButton("자세히 보기")
        self.btn_more_songs.setFixedSize(90, 28)
        self.btn_more_songs.setStyleSheet("font-size: 12px; padding: 2px;")
        self.btn_more_songs.clicked.connect(self.show_more_songs)
        songs_header.addWidget(self.btn_more_songs)
        
        self.top_songs_list = QListWidget()
        songs_vbox.addLayout(songs_header)
        songs_vbox.addWidget(self.top_songs_list)

        # Top Artists Card
        self.artists_card = Card()
        artists_vbox = QVBoxLayout(self.artists_card)
        artists_vbox.setContentsMargins(20, 20, 20, 20)
        
        artists_header = QHBoxLayout()
        artists_title = QLabel("가장 많이 들은 가수 TOP 5")
        artists_title.setStyleSheet(f"font-size: 16px; font-weight: 700;")
        artists_header.addWidget(artists_title)
        artists_header.addStretch()
        
        self.btn_more_artists = QPushButton("자세히 보기")
        self.btn_more_artists.setFixedSize(90, 28)
        self.btn_more_artists.setStyleSheet("font-size: 12px; padding: 2px;")
        self.btn_more_artists.clicked.connect(self.show_more_artists)
        artists_header.addWidget(self.btn_more_artists)
        
        self.top_artists_list = QListWidget()
        artists_vbox.addLayout(artists_header)
        artists_vbox.addWidget(self.top_artists_list)

        bottom_layout.addWidget(self.songs_card)
        bottom_layout.addWidget(self.artists_card)
        self.layout.addLayout(bottom_layout)

    def change_view(self, mode):
        self.view_mode = mode
        self.btn_daily.setChecked(mode == "daily")
        self.btn_weekly.setChecked(mode == "weekly")
        self.btn_monthly.setChecked(mode == "monthly")
        self.update_stats(self.play_history, self.theme_mode)

    def show_more_songs(self):
        if not self.play_history: return
        song_counts = Counter([f"{e['title']} - {e['artist']}" for e in self.play_history])
        items = [f"{song} ({count}회)" for song, count in song_counts.most_common()]
        self.dialog = DetailListDialog("전체 노래 감상 순위", items, self.window())
        self.dialog.show()

    def show_more_artists(self):
        if not self.play_history: return
        artist_counts = Counter([e['artist'] for e in self.play_history if e['artist'] != "Unknown"])
        items = [f"{artist} ({count}회)" for artist, count in artist_counts.most_common()]
        self.dialog = DetailListDialog("전체 가수 감상 순위", items, self.window())
        self.dialog.show()

    def update_stats(self, play_history, theme_mode="light"):
        """통계 데이터를 기반으로 그래프와 리스트를 업데이트합니다."""
        self.play_history = play_history
        self.theme_mode = theme_mode
        if not play_history:
            return

        # 1. 데이터 집계
        today = datetime.now().date()
        counts = Counter()
        data = []
        labels = []
        
        if self.view_mode == "daily":
            self.graph_title.setText("일별 감상 기록 (최근 7일)")
            last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            for entry in play_history:
                try:
                    dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").date()
                    if dt in last_7_days:
                        counts[dt] += 1
                except: continue
            data = [counts.get(d, 0) for d in last_7_days]
            labels = [d.strftime("%m/%d") for d in last_7_days]
            
        elif self.view_mode == "weekly":
            self.graph_title.setText("주별 감상 기록 (최근 8주)")
            start_of_this_week = today - timedelta(days=today.weekday())
            weeks = [start_of_this_week - timedelta(weeks=i) for i in range(7, -1, -1)]
            for entry in play_history:
                try:
                    dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").date()
                    start_of_week = dt - timedelta(days=dt.weekday())
                    if start_of_week in weeks:
                        counts[start_of_week] += 1
                except: continue
            data = [counts.get(w, 0) for w in weeks]
            labels = [f"{w.strftime('%m/%d')}" for w in weeks]

        elif self.view_mode == "monthly":
            self.graph_title.setText("월별 감상 기록 (최근 6개월)")
            months = []
            curr = today.replace(day=1)
            for _ in range(6):
                months.insert(0, curr)
                if curr.month == 1:
                    curr = curr.replace(year=curr.year-1, month=12)
                else:
                    curr = curr.replace(month=curr.month-1)
            
            for entry in play_history:
                try:
                    dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").date().replace(day=1)
                    if dt in months:
                        counts[dt] += 1
                except: continue
            data = [counts.get(m, 0) for m in months]
            labels = [m.strftime("%y/%m") for m in months]

        # 2. 그래프 그리기
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 테마에 따른 색상 설정
        is_dark = theme_mode == "dark"
        text_color = "white" if is_dark else "#14043F"
        bar_color = "#7C4DFF"
        bg_color = "#121212" if is_dark else "white"
        
        self.figure.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        
        bars = ax.bar(labels, data, color=bar_color, alpha=0.7, width=0.6)
        ax.set_ylabel("곡 수", color=text_color, fontsize=10)
        ax.tick_params(axis='x', colors=text_color, labelsize=9)
        ax.tick_params(axis='y', colors=text_color, labelsize=9)
        
        # 테두리 제거
        for spine in ax.spines.values():
            spine.set_visible(False)
            
        # 값 표시
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{int(height)}', ha='center', va='bottom', color=text_color, fontsize=9)

        self.canvas.draw()

        # 3. TOP 5 노래
        song_counts = Counter([f"{e['title']} - {e['artist']}" for e in play_history])
        self.top_songs_list.clear()
        for song, count in song_counts.most_common(5):
            item = QListWidgetItem(f"{song} ({count}회)")
            item.setSizeHint(QSize(0, 40))
            self.top_songs_list.addItem(item)

        # 4. TOP 5 가수
        artist_counts = Counter([e['artist'] for e in play_history if e['artist'] != "Unknown"])
        self.top_artists_list.clear()
        for artist, count in artist_counts.most_common(5):
            item = QListWidgetItem(f"{artist} ({count}회)")
            item.setSizeHint(QSize(0, 40))
            self.top_artists_list.addItem(item)

class HotkeyEdit(QLineEdit):
    changed = Signal(str)

    def __init__(self, current_val, parent=None):
        super().__init__(parent)
        self.setText(current_val)
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.is_recording = False
        self.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px;
                border-radius: 8px;
                border: 1px solid {UIConfig.LIGHT_BORDER};
                background-color: transparent;
                font-weight: 700;
            }}
            QLineEdit:focus {{
                border: 2px solid #7C4DFF;
                background-color: rgba(124, 77, 255, 10%);
            }}
        """)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.start_recording()

    def start_recording(self):
        self.is_recording = True
        self.setText("키 입력 대기 중...")
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_recording:
            return

        key = event.key()
        if key == Qt.Key_Escape:
            self.stop_recording(self.text()) # Cancel
            return

        modifiers = event.modifiers()
        combo = []
        
        if modifiers & Qt.ControlModifier: combo.append("ctrl")
        if modifiers & Qt.ShiftModifier: combo.append("shift")
        if modifiers & Qt.AltModifier: combo.append("alt")
        if modifiers & Qt.MetaModifier: combo.append("win")

        # 실제 키 이름 가져오기
        key_text = QKeySequence(key).toString().lower()
        
        # 특수 키 처리 (QKeySequence가 종종 이상하게 반환함)
        special_keys = {
            Qt.Key_Control: "", Qt.Key_Shift: "", Qt.Key_Alt: "", Qt.Key_Meta: "",
            Qt.Key_CapsLock: "caps lock", Qt.Key_NumLock: "num lock", Qt.Key_ScrollLock: "scroll lock",
            Qt.Key_Print: "print screen", Qt.Key_Pause: "pause", Qt.Key_Insert: "insert",
            Qt.Key_Delete: "delete", Qt.Key_Home: "home", Qt.Key_End: "end",
            Qt.Key_PageUp: "page up", Qt.Key_PageDown: "page down",
            Qt.Key_Left: "left", Qt.Key_Right: "right", Qt.Key_Up: "up", Qt.Key_Down: "down",
            Qt.Key_Backspace: "backspace", Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
            Qt.Key_Tab: "tab", Qt.Key_Space: "space"
        }
        
        if key in special_keys:
            key_name = special_keys[key]
        else:
            key_name = key_text

        if key_name:
            if key_name not in combo:
                combo.append(key_name)
            
            final_hotkey = "+".join(combo)
            self.stop_recording(final_hotkey)
            self.changed.emit(final_hotkey)

    def focusOutEvent(self, event):
        if self.is_recording:
            # 녹화 중 포커스를 잃으면 이전 값으로 복구 (여기선 현재 텍스트 유지)
            self.is_recording = False
        super().focusOutEvent(event)

    def stop_recording(self, val):
        self.is_recording = False
        self.setText(val)
        self.clearFocus()

class SettingPage(QWidget):
    settings_changed = Signal()
    hotkeys_changed = Signal()

    def __init__(self, config_manager: OverlayConfigManager):
        super().__init__()
        self.config = config_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        header = QLabel("오버레이 설정")
        header.setObjectName("PageHeader")
        header.setStyleSheet(f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;")
        layout.addWidget(header)
        
        # Scroll Area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(24)

        # Style Preview at the top
        preview_header = QLabel("오버레이 미리보기")
        preview_header.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: {UIConfig.COLOR_SECONDARY_TEXT}; margin-bottom: -10px;")
        scroll_layout.addWidget(preview_header)
        
        self.preview_area = StylePreview()
        scroll_layout.addWidget(self.preview_area)

        # Control Group (On/Off)
        control_card = Card()
        control_layout = QHBoxLayout(control_card)
        control_layout.setContentsMargins(24, 24, 24, 24)
        
        control_label_vbox = QVBoxLayout()
        control_title = QLabel("오버레이 활성화")
        control_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_M}; font-weight: 800;")
        control_desc = QLabel("가사 오버레이를 화면에 표시하거나 숨깁니다.")
        control_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        control_label_vbox.addWidget(control_title)
        control_label_vbox.addWidget(control_desc)
        
        self.overlay_switch = QCheckBox()
        self.overlay_switch.setCursor(Qt.PointingHandCursor)
        self.overlay_switch.setChecked(self.config.visible)
        self.overlay_switch.toggled.connect(self.on_visible_toggled)
        
        control_layout.addLayout(control_label_vbox)
        control_layout.addStretch()
        control_layout.addWidget(self.overlay_switch)
        scroll_layout.addWidget(control_card)
        
        # Preset Group
        preset_card = Card()
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(24, 24, 24, 24)
        preset_layout.setSpacing(20)

        preset_header = QHBoxLayout()
        preset_title = QLabel("스타일 프리셋")
        preset_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_L}; font-weight: 800; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        preset_header.addWidget(preset_title)
        preset_header.addStretch()
        
        self.btn_save_preset = QPushButton("현재 스타일 저장  💾")
        self.btn_save_preset.setFixedSize(160, 36)
        self.btn_save_preset.clicked.connect(self.save_current_as_preset)
        preset_header.addWidget(self.btn_save_preset)
        preset_layout.addLayout(preset_header)

        # Preset Grid
        self.preset_container = QWidget()
        self.preset_grid = QGridLayout(self.preset_container)
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setSpacing(16)
        
        self.update_preset_list()
        preset_layout.addWidget(self.preset_container)
        
        scroll_layout.addWidget(preset_card)
        
        # Appearance Group
        appearance_card = Card()
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(24, 24, 24, 24)
        appearance_layout.setSpacing(20)
        
        app_title = QLabel("스타일 및 투명도")
        app_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_L}; font-weight: 800; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        appearance_layout.addWidget(app_title)

        # Font Selection
        font_hbox = QHBoxLayout()
        font_label = QLabel("오버레이 글꼴")
        font_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        font_hbox.addWidget(font_label)
        self.btn_font = QPushButton("글꼴 변경  🔤")
        self.btn_font.setObjectName("AccentButton")
        self.btn_font.setFixedSize(140, 40)
        self.btn_font.clicked.connect(self.pick_font)
        font_hbox.addStretch()
        font_hbox.addWidget(self.btn_font)
        appearance_layout.addLayout(font_hbox)
        
        # Transparency
        trans_vbox = QVBoxLayout()
        trans_vbox.setSpacing(12)
        trans_header_layout = QHBoxLayout()
        trans_label = QLabel("오버레이 불투명도")
        trans_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        self.alpha_val_label = QLabel(str(self.config.bg_color.alpha()))
        self.alpha_val_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: #7C4DFF;")
        trans_header_layout.addWidget(trans_label)
        trans_header_layout.addStretch()
        trans_header_layout.addWidget(self.alpha_val_label)
        
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(self.config.bg_color.alpha())
        self.alpha_slider.setFixedHeight(30)
        self.alpha_slider.valueChanged.connect(self.on_alpha_changed)
        
        trans_vbox.addLayout(trans_header_layout)
        trans_vbox.addWidget(self.alpha_slider)
        appearance_layout.addLayout(trans_vbox)

        # Color Settings
        color_grid = QHBoxLayout()
        color_grid.setSpacing(30)
        
        def create_color_ctrl(label_text, color_obj, target):
            vbox = QVBoxLayout()
            vbox.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {UIConfig.COLOR_SECONDARY_TEXT};")
            btn = QPushButton()
            btn.setFixedSize(80, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"background-color: {color_obj.name()}; border-radius: 18px; border: 2px solid #E0E0E0;")
            btn.clicked.connect(lambda: self.pick_color(target, btn))
            vbox.addWidget(lbl)
            vbox.addWidget(btn)
            return vbox, btn

        color_text_vbox, self.btn_text_color = create_color_ctrl("글씨 색상", self.config.text_color, "text")
        color_bg_vbox, self.btn_bg_color = create_color_ctrl("배경 색상", self.config.bg_color, "bg")
        color_out_vbox, self.btn_out_color = create_color_ctrl("아웃라인 색상", self.config.outline_color, "outline")

        color_grid.addLayout(color_text_vbox)
        color_grid.addLayout(color_bg_vbox)
        color_grid.addLayout(color_out_vbox)
        color_grid.addStretch()
        appearance_layout.addLayout(color_grid)

        # Outline Thickness
        outline_vbox = QVBoxLayout()
        outline_vbox.setSpacing(12)
        outline_header = QHBoxLayout()
        outline_label = QLabel("아웃라인 두께")
        outline_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        outline_header.addWidget(outline_label)
        self.outline_val_label = QLabel(str(self.config.outline_width))
        self.outline_val_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: #7C4DFF;")
        outline_header.addStretch()
        outline_header.addWidget(self.outline_val_label)
        
        self.outline_slider = QSlider(Qt.Horizontal)
        self.outline_slider.setRange(0, 10)
        self.outline_slider.setValue(self.config.outline_width)
        self.outline_slider.setFixedHeight(30)
        self.outline_slider.valueChanged.connect(self.on_outline_changed)
        
        outline_vbox.addLayout(outline_header)
        outline_vbox.addWidget(self.outline_slider)
        appearance_layout.addLayout(outline_vbox)

        # Overlay Size
        size_vbox = QVBoxLayout()
        size_vbox.setSpacing(12)
        size_header = QHBoxLayout()
        size_label = QLabel("오버레이 크기 (너비 / 높이)")
        size_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        size_header.addWidget(size_label)
        self.size_val_label = QLabel(f"{self.config.width} x {self.config.height}")
        self.size_val_label.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 800; color: #7C4DFF;")
        size_header.addStretch()
        size_header.addWidget(self.size_val_label)
        
        size_sliders_layout = QHBoxLayout()
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(200, 1500)
        self.width_slider.setValue(self.config.width)
        self.width_slider.setFixedHeight(30)
        self.width_slider.valueChanged.connect(self.on_size_changed)
        
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(80, 500)
        self.height_slider.setValue(self.config.height)
        self.height_slider.setFixedHeight(30)
        self.height_slider.valueChanged.connect(self.on_size_changed)
        
        size_sliders_layout.addWidget(self.width_slider)
        size_sliders_layout.addWidget(self.height_slider)
        
        size_vbox.addLayout(size_header)
        size_vbox.addLayout(size_sliders_layout)
        appearance_layout.addLayout(size_vbox)
        
        scroll_layout.addWidget(appearance_card)
        
        # Interaction Group
        interaction_card = Card()
        interaction_layout = QVBoxLayout(interaction_card)
        interaction_layout.setContentsMargins(24, 24, 24, 24)
        interaction_layout.setSpacing(20)
        
        int_title = QLabel("인식 및 상호작용")
        int_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_L}; font-weight: 800; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        interaction_layout.addWidget(int_title)
        
        # Ghost Mode
        ghost_layout = QHBoxLayout()
        ghost_label_vbox = QVBoxLayout()
        ghost_title = QLabel("고스트 모드")
        ghost_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        ghost_desc = QLabel("오버레이가 마우스 클릭을 통과하도록 설정합니다.")
        ghost_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        ghost_label_vbox.addWidget(ghost_title)
        ghost_label_vbox.addWidget(ghost_desc)
        
        self.ghost_check = QCheckBox()
        self.ghost_check.setCursor(Qt.PointingHandCursor)
        self.ghost_check.setChecked(self.config.ghost_mode)
        self.ghost_check.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
        self.ghost_check.toggled.connect(self.on_ghost_toggled)
        
        ghost_layout.addLayout(ghost_label_vbox)
        ghost_layout.addStretch()
        ghost_layout.addWidget(self.ghost_check)
        interaction_layout.addLayout(ghost_layout)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        line2.setStyleSheet("background-color: #E0E0E0;")
        interaction_layout.addWidget(line2)

        # Move Enabled Toggle
        move_layout = QHBoxLayout()
        move_label_vbox = QVBoxLayout()
        move_title = QLabel("오버레이 위치 이동")
        move_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        move_desc = QLabel("오버레이를 드래그하여 위치를 변경할 수 있도록 합니다.")
        move_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        move_label_vbox.addWidget(move_title)
        move_label_vbox.addWidget(move_desc)
        
        self.move_check = QCheckBox()
        self.move_check.setCursor(Qt.PointingHandCursor)
        self.move_check.setChecked(self.config.move_enabled)
        self.move_check.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
        self.move_check.toggled.connect(self.on_move_toggled)
        
        move_layout.addLayout(move_label_vbox)
        move_layout.addStretch()
        move_layout.addWidget(self.move_check)
        interaction_layout.addLayout(move_layout)

        # Resize Enabled Toggle
        resize_layout = QHBoxLayout()
        resize_label_vbox = QVBoxLayout()
        resize_title = QLabel("오버레이 크기 조절")
        resize_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
        resize_desc = QLabel("오버레이 우측 하단을 드래그하여 크기를 조절할 수 있도록 합니다.")
        resize_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        resize_label_vbox.addWidget(resize_title)
        resize_label_vbox.addWidget(resize_desc)
        
        self.resize_check = QCheckBox()
        self.resize_check.setCursor(Qt.PointingHandCursor)
        self.resize_check.setChecked(self.config.resize_enabled)
        self.resize_check.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
        self.resize_check.toggled.connect(self.on_resize_toggled)
        
        resize_layout.addLayout(resize_label_vbox)
        resize_layout.addStretch()
        resize_layout.addWidget(self.resize_check)
        interaction_layout.addLayout(resize_layout)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #E0E0E0;")
        interaction_layout.addWidget(line)
        
        roi_vbox = QVBoxLayout()
        roi_vbox.setSpacing(12)
        roi_title = QLabel("영역 설정 (비활성화됨)")
        roi_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600; color: #AAAAAA;")
        roi_desc = QLabel("가사가 출력되는 멜론 창의 영역을 직접 선택합니다.")
        roi_desc.setStyleSheet(f"font-size: {UIConfig.FS_DESC}; color: #AAAAAA;")
        
        self.roi_btn = QPushButton("가사 인식 영역 설정 (ROI)  🎯")
        self.roi_btn.setEnabled(False)
        self.roi_btn.setMinimumHeight(55)
        self.roi_btn.setStyleSheet("background-color: #EEEEEE; color: #AAAAAA; border-radius: 10px;")
        
        roi_vbox.addWidget(roi_title)
        roi_vbox.addWidget(roi_desc)
        roi_vbox.addWidget(self.roi_btn)
        interaction_layout.addLayout(roi_vbox)
        
        scroll_layout.addWidget(interaction_card)

        # Hotkeys Group
        hotkey_card = Card()
        hotkey_layout = QVBoxLayout(hotkey_card)
        hotkey_layout.setContentsMargins(24, 24, 24, 24)
        hotkey_layout.setSpacing(20)
        
        hotkey_title = QLabel("단축키 설정")
        hotkey_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_L}; font-weight: 800; color: {UIConfig.COLOR_SECONDARY_TEXT};")
        hotkey_layout.addWidget(hotkey_title)
        
        def create_hotkey_row(label_text, current_val, callback):
            hbox = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600;")
            
            edit = HotkeyEdit(current_val)
            edit.setFixedWidth(150)
            edit.changed.connect(callback)
            
            hbox.addWidget(lbl)
            hbox.addStretch()
            hbox.addWidget(edit)
            return hbox, edit

        ghost_hk_hbox, self.ghost_hk_edit = create_hotkey_row(
            "고스트 모드 토글", self.config.hotkey_ghost, self.on_hotkey_ghost_changed
        )
        quit_hk_hbox, self.quit_hk_edit = create_hotkey_row(
            "프로그램 종료", self.config.hotkey_quit, self.on_hotkey_quit_changed
        )
        
        hotkey_layout.addLayout(ghost_hk_hbox)
        hotkey_layout.addLayout(quit_hk_hbox)
        
        scroll_layout.addWidget(hotkey_card)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Initial Refresh
        self.refresh_ui_from_config()

    def update_preset_list(self):
        # Clear existing grid
        while self.preset_grid.count():
            item = self.preset_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        row = 0
        col = 0
        
        # 시스템 프리셋
        for name, data in self.config.PRESET_STYLES.items():
            preset = PresetItem(name, data, is_custom=False)
            preset.clicked.connect(self.on_preset_selected)
            self.preset_grid.addWidget(preset, row, col)
            col += 1
            if col > 2: # 3 columns
                col = 0
                row += 1
                
        # 사용자 프리셋
        for name, data in self.config.custom_presets.items():
            preset = PresetItem(name, data, is_custom=True)
            preset.clicked.connect(self.on_preset_selected)
            preset.delete_requested.connect(self.on_delete_preset)
            self.preset_grid.addWidget(preset, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

    def on_delete_preset(self, name):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "프리셋 삭제", f"'{name}' 프리셋을 삭제하시겠습니까?", 
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config.delete_custom_preset(name)
            self.update_preset_list()

    def on_preset_selected(self, preset_data):
        self.config.apply_preset(preset_data)
        self.refresh_ui_from_config()
        self.settings_changed.emit()

    def save_current_as_preset(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "프리셋 저장", "프리셋 이름을 입력하세요:")
        if ok and name:
            self.config.save_custom_preset(name)
            self.update_preset_list()

    def refresh_ui_from_config(self):
        """설정 변경 후 UI 요소들의 상태를 업데이트합니다."""
        self.overlay_switch.blockSignals(True)
        self.overlay_switch.setChecked(self.config.visible)
        self.overlay_switch.blockSignals(False)
        
        self.alpha_slider.setValue(self.config.bg_color.alpha())
        self.alpha_val_label.setText(str(self.config.bg_color.alpha()))
        self.outline_slider.setValue(self.config.outline_width)
        self.outline_val_label.setText(str(self.config.outline_width))
        self.width_slider.setValue(self.config.width)
        self.height_slider.setValue(self.config.height)
        self.size_val_label.setText(f"{self.config.width} x {self.config.height}")
        self.ghost_check.setChecked(self.config.ghost_mode)
        self.move_check.setChecked(self.config.move_enabled)
        self.resize_check.setChecked(self.config.resize_enabled)
        
        self.btn_text_color.setStyleSheet(f"background-color: {self.config.text_color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;")
        self.btn_bg_color.setStyleSheet(f"background-color: {self.config.bg_color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;")
        self.btn_out_color.setStyleSheet(f"background-color: {self.config.outline_color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;")
        
        # Update Preview Area
        self.preview_area.update_preview(self.config)

    def on_visible_toggled(self, checked):
        self.config.visible = checked
        self.settings_changed.emit()

    def on_ghost_toggled(self, checked):
        self.config.ghost_mode = checked
        self.settings_changed.emit()

    def on_move_toggled(self, checked):
        self.config.set_move_enabled(checked)
        self.settings_changed.emit()

    def on_resize_toggled(self, checked):
        self.config.set_resize_enabled(checked)
        self.settings_changed.emit()

    def on_hotkey_ghost_changed(self, text):
        self.config.update_hotkey_ghost(text.strip())
        self.settings_changed.emit()
        self.hotkeys_changed.emit()

    def on_hotkey_quit_changed(self, text):
        self.config.update_hotkey_quit(text.strip())
        self.settings_changed.emit()
        self.hotkeys_changed.emit()

    def on_alpha_changed(self, value):
        self.alpha_val_label.setText(str(value))
        self.config.update_background(opacity=value)
        self.settings_changed.emit()

    def on_outline_changed(self, value):
        self.outline_val_label.setText(str(value))
        self.config.update_text_style(outline_width=value)
        self.settings_changed.emit()

    def on_size_changed(self):
        w = self.width_slider.value()
        h = self.height_slider.value()
        self.size_val_label.setText(f"{w} x {h}")
        self.config.update_size(w, h)
        self.settings_changed.emit()

    def pick_color(self, target, btn):
        current_color = getattr(self.config, f"{target}_color")
        color = QColorDialog.getColor(current_color)
        if color.isValid():
            btn.setStyleSheet(f"background-color: {color.name()}; border-radius: 18px; border: 2px solid #E0E0E0;")
            if target == "text":
                self.config.update_text_style(color=color)
            elif target == "bg":
                self.config.update_background(color=color)
            elif target == "outline":
                self.config.update_text_style(outline_color=color)
            self.settings_changed.emit()

    def pick_font(self):
        current_font = QFont(self.config.font_family, self.config.font_size)
        ok, font = QFontDialog.getFont(current_font, self)
        if ok:
            self.config.update_font(family=font.family(), size=font.pointSize())
            self.settings_changed.emit()

class MainWindow(QMainWindow):
    theme_changed = Signal(str)

    def __init__(self, stats, initial_theme="light"):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        self.setFixedSize(1280, 720)
        self.persistent_stats = stats
        
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "asset", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self.theme_manager = ThemeManager()
        if initial_theme == "dark":
            self.theme_manager.current_theme = Theme.DARK
            
        self.config_manager = OverlayConfigManager()
        self.overlay = LyricsOverlay(self.config_manager)
        
        self.load_fonts()
        self.setup_ui()
        self.apply_theme(self.theme_manager.current_theme)
        
        self.overlay.show()

    def load_fonts(self):
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "asset", "Font")
        if os.path.exists(font_dir):
            for font_file in os.listdir(font_dir):
                if font_file.endswith(".ttf"):
                    QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
        
        self.default_font = QFont("Pretendard", 10)
        QApplication.setFont(self.default_font)

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(16, 24, 16, 24)
        self.sidebar_layout.setSpacing(8)
        
        menu_label = QLabel("메뉴")
        menu_label.setObjectName("SidebarMenuLabel")
        self.sidebar_layout.addWidget(menu_label)
        
        self.btn_dashboard = SidebarButton("대시보드  🏠", UIConfig.ICON_COLOR_DASHBOARD)
        self.btn_music = SidebarButton("가사 목록  🎵", UIConfig.ICON_COLOR_MUSIC)
        self.btn_stats = SidebarButton("통계  📊", UIConfig.ICON_COLOR_STATS)
        self.btn_settings = SidebarButton("설정  ⚙️", UIConfig.ICON_COLOR_SETTINGS)
        
        self.sidebar_layout.addWidget(self.btn_dashboard)
        self.sidebar_layout.addWidget(self.btn_music)
        self.sidebar_layout.addWidget(self.btn_stats)
        self.sidebar_layout.addWidget(self.btn_settings)
        
        self.sidebar_layout.addStretch()
        
        self.btn_theme = QPushButton("🌓  테마 전환")
        self.btn_theme.setObjectName("ThemeButton")
        self.btn_theme.setMinimumHeight(50)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.sidebar_layout.addWidget(self.btn_theme)
        
        self.content_stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.music_page = MusicListPage()
        self.stats_page = StatsPage()
        self.setting_page = SettingPage(self.config_manager)
        
        self.setting_page.settings_changed.connect(self.update_overlay)
        
        self.content_stack.addWidget(self.dashboard_page)
        self.content_stack.addWidget(self.music_page)
        self.content_stack.addWidget(self.stats_page)
        self.content_stack.addWidget(self.setting_page)
        
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_stack)

        self.nav_buttons = [self.btn_dashboard, self.btn_music, self.btn_stats, self.btn_settings]
        self.btn_dashboard.setChecked(True)
        
        self.btn_dashboard.clicked.connect(lambda: self.switch_page(0))
        self.btn_music.clicked.connect(lambda: self.switch_page(1))
        self.btn_stats.clicked.connect(lambda: self.switch_page(2))
        self.btn_settings.clicked.connect(lambda: self.switch_page(3))

    def update_overlay(self):
        self.overlay.sync_with_config()

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)
        
        # 통계 페이지로 전환 시 데이터 업데이트
        if index == 2:
            theme_mode = "dark" if self.theme_manager.current_theme == Theme.DARK else "light"
            self.stats_page.update_stats(self.persistent_stats.get("play_history", []), theme_mode)

    def toggle_theme(self):
        new_theme = self.theme_manager.toggle_theme()
        self.apply_theme(new_theme)
        theme_name = "light" if new_theme == Theme.LIGHT else "dark"
        self.theme_changed.emit(theme_name)
        
        # 테마 변경 시 통계 그래프도 다시 그리기
        if self.content_stack.currentIndex() == 2:
            self.stats_page.update_stats(self.persistent_stats.get("play_history", []), theme_name)

    def apply_theme(self, theme):
        style = f"""
            QMainWindow, QWidget {{
                background-color: {theme["bg_main"]};
                color: {theme["text_primary"]};
                font-family: 'Pretendard';
            }}
            QFrame#Sidebar {{
                background-color: {theme["bg_sidebar"]};
                border-right: 1px solid {theme["border"]};
            }}
            QLabel#SidebarMenuLabel {{
                font-size: {UIConfig.FS_SIDEBAR_TITLE};
                font-family: 'Pretendard SemiBold', 'Pretendard';
                font-weight: 800;
                margin-bottom: 20px;
                padding-left: 12px;
                color: {theme["text_primary"]};
                letter-spacing: -0.5px;
                background-color: transparent;
            }}
            QFrame#Card {{
                background-color: {theme["bg_card"]};
                border-radius: 16px;
                border: 1px solid {theme["border"]};
            }}
            QPushButton {{
                background-color: {theme["btn_bg"]};
                color: {theme["btn_text"]};
                border: 1px solid {theme["btn_border"]};
                border-radius: 10px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: {UIConfig.FS_BUTTON};
            }}
            QPushButton:hover {{
                background-color: {theme["sb_hover_bg"]};
                border: 1px solid {theme["accent"]};
            }}
            QPushButton#ThemeButton {{
                background-color: {theme["accent"]};
                color: white;
                border: none;
                font-size: {UIConfig.FS_THEME_BUTTON};
                margin-top: 10px;
            }}
            QPushButton#ThemeButton:hover {{
                background-color: {theme["accent_hover"]};
            }}
            SidebarButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                text-align: left;
                padding-left: 55px;
                font-family: 'Pretendard SemiBold', 'Pretendard';
                font-weight: 600;
                font-size: {UIConfig.FS_SIDEBAR_BTN};
                color: {theme["sb_normal_text"]};
                margin: 2px 0px;
            }}
            SidebarButton:hover {{
                background-color: {theme["sb_hover_bg"]};
                color: {theme["text_primary"]};
            }}
            SidebarButton:checked {{
                background-color: {theme["sb_active_bg"]};
                color: {theme["sb_active_text"]};
                font-family: 'Pretendard SemiBold', 'Pretendard';
                font-weight: 800;
            }}
            QListWidget {{
                color: {theme["text_primary"]};
                background-color: transparent;
                border: none;
                font-size: {UIConfig.FS_LIST};
                outline: none;
            }}
            QListWidget::item {{
                padding: 12px;
                border-radius: 8px;
            }}
            QListWidget::item:hover {{
                background-color: {theme["sb_hover_bg"]};
            }}
            QListWidget::item:selected {{
                background-color: {theme["list_sel_bg"]};
                color: {theme["list_sel_text"]};
            }}
            QLabel#PageHeader {{
                color: {theme["text_primary"]};
                font-weight: 900;
                letter-spacing: -1px;
                margin-bottom: 20px;
            }}
            QPushButton#AccentButton {{
                background-color: {theme["btn_font_bg"]};
                color: {theme["btn_font_text"]};
                border: none;
                font-weight: 700;
            }}
            QPushButton#AccentButton:hover {{
                background-color: {theme["accent_hover"]};
            }}
            QCheckBox {{
                spacing: 12px;
                font-size: {UIConfig.FS_CHECKBOX};
                font-weight: 500;
            }}
            QCheckBox::indicator {{
                width: 24px;
                height: 24px;
                border-radius: 6px;
                border: 2px solid {theme["btn_border"]};
                background-color: {theme["bg_card"]};
            }}
            QCheckBox::indicator:checked {{
                background-color: {theme["accent"]};
                border: 2px solid {theme["accent"]};
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid {theme["accent"]};
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {theme["btn_border"]};
                height: 6px;
                background: {theme["sb_hover_bg"]};
                margin: 2px 0;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {theme["accent"]};
                border: none;
                width: 18px;
                height: 18px;
                margin: -7px 0;
                border-radius: 9px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """
        self.central_widget.setStyleSheet(style)
