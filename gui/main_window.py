"""메인 윈도우 — 사이드바 + 페이지 스택."""

import os
import sys

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtGui import QFont, QFontDatabase, QIcon  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.theme import Theme, ThemeManager, UIConfig
from gui.pages.dashboard_page import DashboardPage
from gui.pages.music_list_page import MusicListPage
from gui.pages.stats_page import StatsPage
from gui.pages.setting_page import SettingPage
from overlay.config_manager import OverlayConfigManager
from overlay.lyrics_overlay import LyricsOverlay


class SidebarButton(QPushButton):
    """사이드바 내비게이션 버튼."""

    def __init__(self, text: str, icon_color: str = "#000000", parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(55)
        self.setCursor(Qt.PointingHandCursor)

        self.icon_circle = QFrame(self)
        self.icon_circle.setFixedSize(16, 16)
        self.icon_circle.setStyleSheet(
            f"background-color: {icon_color}; border-radius: 8px; border: none;"
        )
        self.icon_circle.move(20, 19)
        self.icon_circle.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setContentsMargins(50, 0, 0, 0)


class MainWindow(QMainWindow):
    """애플리케이션 메인 윈도우."""

    theme_changed = Signal(str)

    def __init__(self, stats: dict, initial_theme: str = "light"):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        self.setFixedSize(1280, 720)
        self.persistent_stats = stats

        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "asset", "logo.png"
        )
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self.theme_manager = ThemeManager()
        if initial_theme == "dark":
            self.theme_manager.current_theme = Theme.DARK

        self.config_manager = OverlayConfigManager()
        self.overlay = LyricsOverlay(self.config_manager)

        self._load_fonts()
        self._setup_ui()
        self.apply_theme(self.theme_manager.current_theme)
        self.overlay.show()

    # ------------------------------------------------------------------ #
    # 초기화
    # ------------------------------------------------------------------ #

    def _load_fonts(self) -> None:
        font_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "asset", "Font"
        )
        if os.path.exists(font_dir):
            for font_file in os.listdir(font_dir):
                if font_file.endswith(".ttf"):
                    QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
        font = QFont("Pretendard", 10)
        font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        font.setHintingPreference(QFont.PreferNoHinting)
        QApplication.setFont(font)

    def _setup_ui(self) -> None:
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 사이드바
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(8)

        menu_label = QLabel("메뉴")
        menu_label.setObjectName("SidebarMenuLabel")
        sidebar_layout.addWidget(menu_label)

        self.btn_dashboard = SidebarButton("대시보드  🏠", UIConfig.ICON_COLOR_DASHBOARD)
        self.btn_music = SidebarButton("가사 목록  🎵", UIConfig.ICON_COLOR_MUSIC)
        self.btn_stats = SidebarButton("통계  📊", UIConfig.ICON_COLOR_STATS)
        self.btn_settings = SidebarButton("설정  ⚙️", UIConfig.ICON_COLOR_SETTINGS)

        for btn in [self.btn_dashboard, self.btn_music, self.btn_stats, self.btn_settings]:
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()

        self.btn_theme = QPushButton("🌓  테마 전환")
        self.btn_theme.setObjectName("ThemeButton")
        self.btn_theme.setMinimumHeight(50)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.btn_theme)

        # 콘텐츠 스택
        self.content_stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.music_page = MusicListPage()
        self.stats_page = StatsPage()
        self.setting_page = SettingPage(self.config_manager)

        self.setting_page.settings_changed.connect(self.update_overlay)

        self.content_stack.addWidget(self.dashboard_page)  # index 0
        self.content_stack.addWidget(self.music_page)       # index 1
        self.content_stack.addWidget(self.stats_page)       # index 2
        self.content_stack.addWidget(self.setting_page)     # index 3

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content_stack)

        self.nav_buttons = [
            self.btn_dashboard, self.btn_music, self.btn_stats, self.btn_settings
        ]
        self.btn_dashboard.setChecked(True)
        self.btn_dashboard.clicked.connect(lambda: self.switch_page(0))
        self.btn_music.clicked.connect(lambda: self.switch_page(1))
        self.btn_stats.clicked.connect(lambda: self.switch_page(2))
        self.btn_settings.clicked.connect(lambda: self.switch_page(3))

    # ------------------------------------------------------------------ #
    # 공개 메서드
    # ------------------------------------------------------------------ #

    def update_overlay(self) -> None:
        """설정 변경 시 오버레이에 동기화합니다."""
        self.overlay.sync_with_config()

    def switch_page(self, index: int) -> None:
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)
        # 통계 페이지 전환 시 데이터 업데이트
        if index == 2:
            theme_mode = (
                "dark" if self.theme_manager.current_theme == Theme.DARK else "light"
            )
            self.stats_page.update_stats(
                self.persistent_stats.get("play_history", []), theme_mode
            )

    def toggle_theme(self) -> None:
        new_theme = self.theme_manager.toggle_theme()
        self.apply_theme(new_theme)
        theme_name = "light" if new_theme == Theme.LIGHT else "dark"
        self.theme_changed.emit(theme_name)
        if self.content_stack.currentIndex() == 2:
            self.stats_page.update_stats(
                self.persistent_stats.get("play_history", []), theme_name
            )

    def apply_theme(self, theme: dict) -> None:
        """전체 위젯에 테마 스타일시트를 적용합니다."""
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
                font-family: 'Pretendard';
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
                font-family: 'Pretendard';
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
                font-family: 'Pretendard';
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
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {theme["btn_border"]};
                min-height: 30px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {theme["text_secondary"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: transparent;
                height: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {theme["btn_border"]};
                min-width: 30px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {theme["text_secondary"]};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """
        self.central_widget.setStyleSheet(style)


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app = QApplication(sys.argv)
    win = MainWindow(stats={})
    win.show()
    sys.exit(app.exec())
