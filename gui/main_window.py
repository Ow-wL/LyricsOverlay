"""메인 윈도우 — 떠 있는 유리 사이드바 + 페이지 스택."""

import ctypes
import os
import sys

from PySide6.QtCore import QRectF, Qt, Signal  # type: ignore
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui import icons
from gui import theme as theme_mod
from gui.style import build_stylesheet
from gui.theme import Theme, ThemeManager
from gui.widgets.card import Card
from gui.widgets.glass import GlassBackground, NavButton, ToggleSwitch, label
from gui.pages.dashboard_page import DashboardPage
from gui.pages.music_list_page import MusicListPage
from gui.pages.stats_page import StatsPage
from gui.pages.setting_page import SettingPage
from gui.pages.info_page import InfoPage
from overlay.config_manager import OverlayConfigManager
from overlay.lyrics_overlay import LyricsOverlay
from core.utils import resource_path


class BrandMark(QWidget):
    """사이드바 상단의 작은 로고 (그라데이션 사각형 + 음표)."""

    def __init__(self, size: int = 38, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        t = theme_mod.active()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, QColor(t["accent"]))
        grad.setColorAt(1, QColor(t["accent_2"]))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(r, 11, 11)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(icons.icon_font(18))
        p.drawText(r, Qt.AlignCenter, icons.MUSIC)


class MainWindow(QMainWindow):
    """애플리케이션 메인 윈도우."""

    theme_changed = Signal(str)
    window_closed = Signal()
    quit_requested = Signal()  # 트레이 메뉴의 '종료'

    def __init__(self, stats: dict, app_config, initial_theme: str = "light"):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        self.setFixedSize(1280, 720)
        self.persistent_stats = stats

        icon_path = resource_path(os.path.join("asset", "icon.ico"))
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)

        self.theme_manager = ThemeManager()
        if initial_theme == "dark":
            self.theme_manager.current_theme = Theme.DARK
        theme_mod.set_active(self.theme_manager.current_theme)

        self.app_config = app_config
        self.config_manager = OverlayConfigManager(app_config.data_dir)
        self.overlay = LyricsOverlay(self.config_manager)

        self._load_fonts()
        self._setup_ui()
        self.apply_theme(self.theme_manager.current_theme)
        self._setup_tray()
        self._tray_notice_shown = False
        self._quitting = False

    # ------------------------------------------------------------------ #
    # 초기화
    # ------------------------------------------------------------------ #

    def _load_fonts(self) -> None:
        font_dir = resource_path(os.path.join("asset", "Font"))
        if os.path.exists(font_dir):
            for font_file in os.listdir(font_dir):
                if font_file.endswith(".ttf"):
                    QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
        font = QFont("Pretendard")
        font.setPixelSize(14)
        font.setStyleStrategy(
            QFont.PreferAntialias | QFont.PreferQuality | QFont.NoSubpixelAntialias
        )
        font.setHintingPreference(QFont.PreferNoHinting)
        QApplication.setFont(font)

    def _setup_ui(self) -> None:
        self.central_widget = GlassBackground()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(18, 18, 0, 18)
        main_layout.setSpacing(8)

        # ── 사이드바 (떠 있는 유리 패널)
        self.sidebar = Card()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(232)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 22, 16, 16)
        sidebar_layout.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.setContentsMargins(6, 0, 0, 0)
        brand.addWidget(BrandMark())
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_text.addWidget(label("Lyrics Overlay", "BrandName"))
        brand_text.addWidget(label("실시간 가사 오버레이", "Tertiary", "font-size: 12px;"))
        brand.addLayout(brand_text)
        brand.addStretch()
        sidebar_layout.addLayout(brand)
        sidebar_layout.addSpacing(28)

        menu_label = label("메뉴", "SectionLabel")
        menu_label.setContentsMargins(10, 0, 0, 6)
        sidebar_layout.addWidget(menu_label)

        self.btn_dashboard = NavButton(icons.HOME, "대시보드")
        self.btn_music = NavButton(icons.PLAYLIST, "감상 기록")
        self.btn_stats = NavButton(icons.CHART, "통계")
        self.btn_settings = NavButton(icons.SETTINGS, "설정")
        self.btn_info = NavButton(icons.INFO, "정보")
        for btn in [self.btn_dashboard, self.btn_music, self.btn_stats, self.btn_settings, self.btn_info]:
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()

        # 테마 전환 스위치
        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(12, 10, 6, 4)
        self.theme_glyph = label(icons.MOON, "IconGlyph", "font-size: 15px;")
        theme_row.addWidget(self.theme_glyph)
        theme_row.addSpacing(6)
        theme_row.addWidget(label("다크 모드", "Secondary", "font-weight: 600;"))
        theme_row.addStretch()
        self.theme_switch = ToggleSwitch()
        self.theme_switch.setChecked(self.theme_manager.current_theme is Theme.DARK)
        self.theme_switch.toggled.connect(self._on_theme_switch)
        theme_row.addWidget(self.theme_switch)
        sidebar_layout.addLayout(theme_row)

        # ── 콘텐츠 스택
        self.content_stack = QStackedWidget()
        self.dashboard_page = DashboardPage(self.config_manager)
        self.music_page = MusicListPage()
        self.stats_page = StatsPage()
        self.setting_page = SettingPage(self.config_manager, self.app_config)
        self.info_page = InfoPage()

        self.setting_page.settings_changed.connect(self.update_overlay)

        self.content_stack.addWidget(self.dashboard_page)  # index 0
        self.content_stack.addWidget(self.music_page)       # index 1
        self.content_stack.addWidget(self.stats_page)       # index 2
        self.content_stack.addWidget(self.setting_page)     # index 3
        self.content_stack.addWidget(self.info_page)        # index 4

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content_stack, 1)

        self.nav_buttons = [
            self.btn_dashboard, self.btn_music, self.btn_stats, self.btn_settings, self.btn_info
        ]
        self.btn_dashboard.setChecked(True)
        self.btn_dashboard.clicked.connect(lambda: self.switch_page(0))
        self.btn_music.clicked.connect(lambda: self.switch_page(1))
        self.btn_stats.clicked.connect(lambda: self.switch_page(2))
        self.btn_settings.clicked.connect(lambda: self.switch_page(3))
        self.btn_info.clicked.connect(lambda: self.switch_page(4))

    # ------------------------------------------------------------------ #
    # 공개 메서드
    # ------------------------------------------------------------------ #

    def _setup_tray(self) -> None:
        """트레이 아이콘: 창을 닫아도 가사 오버레이는 계속 실행됩니다."""
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip("Lyrics Overlay")
        menu = QMenu(self)
        menu.addAction("창 열기", self.show_from_tray)
        self.tray_overlay_action = menu.addAction("오버레이 표시", self._tray_toggle_overlay)
        self.tray_overlay_action.setCheckable(True)
        self.tray_ghost_action = menu.addAction("고스트 모드 (클릭 통과)", self._tray_toggle_ghost)
        self.tray_ghost_action.setCheckable(True)
        menu.addSeparator()
        menu.addAction("종료", self.request_quit)
        menu.aboutToShow.connect(self._sync_tray_menu)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self.tray = tray

    def _sync_tray_menu(self) -> None:
        self.tray_overlay_action.setChecked(self.config_manager.visible)
        self.tray_ghost_action.setChecked(self.config_manager.ghost_mode)

    def _tray_toggle_overlay(self) -> None:
        self.config_manager.set_visible(not self.config_manager.visible)
        self.setting_page.refresh_ui_from_config()
        self.update_overlay()

    def _tray_toggle_ghost(self) -> None:
        self.config_manager.set_ghost_mode(not self.config_manager.ghost_mode)
        self.setting_page.refresh_ui_from_config()
        self.update_overlay()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_from_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def request_quit(self) -> None:
        self._quitting = True
        self.quit_requested.emit()

    def closeEvent(self, event) -> None:
        """X 버튼: 설정에 따라 트레이로 숨기거나 프로그램을 종료합니다."""
        if not self._quitting and self.tray is not None and self.config_manager.close_to_tray:
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self._tray_notice_shown = True
                self.tray.showMessage(
                    "Lyrics Overlay",
                    "트레이에서 계속 실행 중이에요. 아이콘을 클릭하면 창이 다시 열립니다.",
                    QSystemTrayIcon.Information, 3000,
                )
            return
        self.window_closed.emit()
        if self.tray is not None:
            self.tray.hide()
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.close()
        super().closeEvent(event)

    def update_overlay(self) -> None:
        """설정 변경 시 오버레이에 동기화합니다."""
        self.overlay.sync_with_config()

    def switch_page(self, index: int) -> None:
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)
        # 통계 페이지 전환 시 데이터 업데이트
        if index == 2:
            self.stats_page.update_stats(
                self.persistent_stats.get("play_history", []),
                self.theme_manager.current_theme["name"],
            )

    def _on_theme_switch(self, checked: bool) -> None:
        if (self.theme_manager.current_theme is Theme.DARK) != checked:
            self.toggle_theme()

    def toggle_theme(self) -> None:
        new_theme = self.theme_manager.toggle_theme()
        self.apply_theme(new_theme)
        theme_name = new_theme["name"]
        self.theme_changed.emit(theme_name)
        if self.content_stack.currentIndex() == 2:
            self.stats_page.update_stats(
                self.persistent_stats.get("play_history", []), theme_name
            )

    def apply_theme(self, theme: dict) -> None:
        """테마 토큰으로 스타일시트를 다시 만들고, 직접 그리는 위젯도 갱신합니다."""
        theme_mod.set_active(theme)
        self.central_widget.setStyleSheet(build_stylesheet(theme))
        for card in self.findChildren(Card):
            card.refresh_theme()
        self.theme_switch.blockSignals(True)
        self.theme_switch.setChecked(theme is Theme.DARK)
        self.theme_switch.blockSignals(False)
        self.theme_glyph.setText(icons.MOON if theme is Theme.DARK else icons.SUN)
        self._apply_title_bar(theme)
        for w in [self.central_widget, *self.central_widget.findChildren(QWidget)]:
            w.update()

    def _apply_title_bar(self, theme: dict) -> None:
        """Windows 10/11 제목 표시줄 색을 테마에 맞춥니다 (지원하지 않으면 무시)."""
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            dark = ctypes.c_int(1 if theme is Theme.DARK else 0)
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            c = QColor(theme["bg_top"])
            colorref = ctypes.c_uint(c.red() | (c.green() << 8) | (c.blue() << 16))
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), ctypes.sizeof(colorref))
        except Exception:
            pass


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app = QApplication(sys.argv)

    class _TmpConfig:
        data_dir = os.getcwd()

    win = MainWindow(stats={}, app_config=_TmpConfig())
    win.show()
    sys.exit(app.exec())
