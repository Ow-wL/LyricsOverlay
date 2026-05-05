import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QFrame, QListWidget, QSlider, QCheckBox, QGroupBox,
                             QListWidgetItem, QGraphicsDropShadowEffect, QScrollArea)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QIcon, QColor, QFont, QPixmap, QFontDatabase

# Set up path for independent execution
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.roi_selector import ROISelector

class Theme:
    LIGHT = {
        "bg_main": "#FFFFFF",
        "bg_sidebar": "#F8F9FA",
        "bg_card": "#FFFFFF",
        "border": "#E0E0E0",
        "text_primary": "#14043F",
        "text_secondary": "#555555",
        "accent": "#14043F",
        "accent_hover": "#2A1066",
        "success": "#4CAF50",
        "danger": "#F44336",
        "sidebar_active": "#EEEEEE"
    }
    DARK = {
        "bg_main": "#121212",
        "bg_sidebar": "#1E1E1E",
        "bg_card": "#242424",
        "border": "#333333",
        "text_primary": "#FFFFFF",
        "text_secondary": "#AAAAAA",
        "accent": "#7C4DFF",
        "accent_hover": "#9E7BFF",
        "success": "#66BB6A",
        "danger": "#EF5350",
        "sidebar_active": "#333333"
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
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

class SidebarButton(QPushButton):
    def __init__(self, text, icon_color="#000000", parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(50)
        self.setCursor(Qt.PointingHandCursor)
        self.icon_circle = QFrame(self)
        self.icon_circle.setFixedSize(24, 24)
        self.icon_circle.setStyleSheet(f"background-color: {icon_color}; border-radius: 12px;")
        self.icon_circle.move(16, 13)
        self.setContentsMargins(50, 0, 0, 0)

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(32)

        # Header
        header = QLabel("대시보드")
        header.setObjectName("PageHeader")
        header.setStyleSheet("font-size: 36px; font-weight: 900;")
        self.layout.addWidget(header)

        # Stats Row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        
        self.stat1 = self.create_stat_card("들은 노래 수", "127곡", "전 주 대비 21% 증가")
        self.stat2 = self.create_stat_card("노래 플레이 타임", "2,301분", "전 주 대비 12% 증가")
        self.stat3 = self.create_stat_card("들은 가수의 수", "31명", "전월 대비 -8% 감소")
        
        stats_layout.addWidget(self.stat1)
        stats_layout.addWidget(self.stat2)
        stats_layout.addWidget(self.stat3)
        self.layout.addLayout(stats_layout)

        # Bottom Row
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(24)

        # Lyrics Preview Card
        self.lyrics_card = Card()
        lyrics_vbox = QVBoxLayout(self.lyrics_card)
        lyrics_vbox.setContentsMargins(24, 24, 24, 24)
        
        lyrics_title = QLabel("실시간 가사 미리보기")
        lyrics_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        
        self.curr_lyric = QLabel("그대 반드시 행복해지세요\n그 다음 말은 이젠")
        self.curr_lyric.setAlignment(Qt.AlignCenter)
        self.curr_lyric.setStyleSheet("font-size: 32px; font-weight: 400; line-height: 48px;")
        self.curr_lyric.setWordWrap(True)
        
        lyrics_vbox.addWidget(lyrics_title)
        lyrics_vbox.addStretch()
        lyrics_vbox.addWidget(self.curr_lyric)
        lyrics_vbox.addStretch()
        
        # Log Card
        self.log_card = Card()
        self.log_card.setFixedWidth(400)
        log_vbox = QVBoxLayout(self.log_card)
        log_vbox.setContentsMargins(24, 24, 24, 24)
        
        log_title = QLabel("시스템 로그")
        log_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        
        self.log_list = QListWidget()
        self.log_list.setStyleSheet("background: transparent; border: none;")
        self.log_list.addItem("[14:20:05] 프로그램 시작")
        self.log_list.addItem("[14:20:06] Melon 창 감지됨")
        self.log_list.addItem("[14:20:10] 가사 매칭 완료")
        
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
        t.setStyleSheet("font-size: 16px; font-weight: 600; color: #828282;")
        v = QLabel(value)
        v.setStyleSheet("font-size: 40px; font-weight: 600;")
        s = QLabel(sub)
        s.setStyleSheet("font-size: 14px; color: #828282;")
        
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
        header.setStyleSheet("font-size: 36px; font-weight: 900;")
        layout.addWidget(header)
        layout.addSpacing(20)
        
        self.list_card = Card()
        card_layout = QVBoxLayout(self.list_card)
        
        self.music_list = QListWidget()
        self.music_list.setStyleSheet("background: transparent; border: none;")
        
        items = [
            ("사랑하게 될거야", "한로로", "26.04.04"),
            ("WE LIKE 2 PARTY", "BIGBANG(빅뱅)", "26.04.03"),
            ("Drowning", "WOODZ", "26.04.02"),
            ("그대 작은 나의 세상이 되어", "카더가든", "26.04.02")
        ]
        
        for title, artist, date in items:
            item = QListWidgetItem(f"{title} - {artist} ({date})")
            item.setSizeHint(QSize(0, 60))
            self.music_list.addItem(item)
            
        card_layout.addWidget(self.music_list)
        layout.addWidget(self.list_card)

class SettingPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        header = QLabel("오버레이 설정")
        header.setStyleSheet("font-size: 36px; font-weight: 900;")
        layout.addWidget(header)
        layout.addSpacing(20)
        
        settings_card = Card()
        card_layout = QVBoxLayout(settings_card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(24)
        
        # Transparency
        card_layout.addWidget(QLabel("오버레이 투명도"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(200)
        card_layout.addWidget(self.alpha_slider)
        
        # Ghost Mode
        self.ghost_check = QCheckBox("고스트 모드 (클릭 통과)")
        self.ghost_check.setChecked(True)
        card_layout.addWidget(self.ghost_check)
        
        # ROI Selection Button
        self.roi_btn = QPushButton("가사 인식 영역 설정 (ROI)")
        self.roi_btn.setMinimumHeight(50)
        self.roi_btn.setCursor(Qt.PointingHandCursor)
        self.roi_btn.clicked.connect(self.start_roi_selection)
        card_layout.addWidget(self.roi_btn)
        
        card_layout.addStretch()
        layout.addWidget(settings_card)
        layout.addStretch()

    def start_roi_selection(self):
        self.selector = ROISelector()
        self.selector.show()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        self.setFixedSize(1280, 720)
        
        self.theme_manager = ThemeManager()
        self.load_fonts()
        self.setup_ui()
        self.apply_theme(self.theme_manager.current_theme)

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

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(280)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(16, 24, 16, 24)
        self.sidebar_layout.setSpacing(8)
        
        menu_label = QLabel("메뉴")
        menu_label.setStyleSheet("font-size: 24px; font-weight: 600; margin-bottom: 20px; padding-left: 8px;")
        self.sidebar_layout.addWidget(menu_label)
        
        self.btn_dashboard = SidebarButton("대시보드", "#F17979")
        self.btn_music = SidebarButton("가사 목록", "#7EEFB1")
        self.btn_settings = SidebarButton("설정", "#F1F175")
        
        self.sidebar_layout.addWidget(self.btn_dashboard)
        self.sidebar_layout.addWidget(self.btn_music)
        self.sidebar_layout.addWidget(self.btn_settings)
        
        self.sidebar_layout.addStretch()
        
        # Theme Toggle Button
        self.btn_theme = QPushButton("테마 전환 (다크/라이트)")
        self.btn_theme.setMinimumHeight(50)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.sidebar_layout.addWidget(self.btn_theme)
        
        # Content Area
        self.content_stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.music_page = MusicListPage()
        self.setting_page = SettingPage()
        
        self.content_stack.addWidget(self.dashboard_page)
        self.content_stack.addWidget(self.music_page)
        self.content_stack.addWidget(self.setting_page)
        
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_stack)

        # Button Grouping
        self.nav_buttons = [self.btn_dashboard, self.btn_music, self.btn_settings]
        self.btn_dashboard.setChecked(True)
        
        self.btn_dashboard.clicked.connect(lambda: self.switch_page(0))
        self.btn_music.clicked.connect(lambda: self.switch_page(1))
        self.btn_settings.clicked.connect(lambda: self.switch_page(2))

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)

    def toggle_theme(self):
        new_theme = self.theme_manager.toggle_theme()
        self.apply_theme(new_theme)

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
            QFrame#Card {{
                background-color: {theme["bg_card"]};
                border-radius: 12px;
                border: 1px solid {theme["border"]};
            }}
            SidebarButton {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 60px;
                font-weight: 600;
                font-size: 17px;
                color: {theme["text_primary"]};
            }}
            SidebarButton:hover {{
                background-color: {theme["sidebar_active"]};
            }}
            SidebarButton:checked {{
                background-color: {theme["sidebar_active"]};
                color: {theme["accent"]};
                font-weight: 800;
            }}
            QPushButton {{
                background-color: {theme["accent"]};
                color: white;
                border-radius: 8px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {theme["accent_hover"]};
            }}
            QListWidget {{
                color: {theme["text_primary"]};
                font-size: 15px;
            }}
            QLabel#PageHeader {{
                color: {theme["text_primary"]};
                margin-bottom: 10px;
            }}
            QCheckBox, QSlider {{
                color: {theme["text_primary"]};
            }}
            QLabel {{
                color: {theme["text_primary"]};
            }}
        """
        self.central_widget.setStyleSheet(style)
        self.sidebar.setStyleSheet(f"background-color: {theme['bg_sidebar']}; border-right: 1px solid {theme['border']};")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
