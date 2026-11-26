"""메인 윈도우 — 떠 있는 유리 사이드바 + 페이지 스택."""

import ctypes
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Signal  # type: ignore
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPixmap  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QFileDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui import icons, typography
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
from core.version import APP_VERSION


class BrandMark(QWidget):
    """사이드바 상단 로고 마크.

    asset/brand_mark.png가 있으면 그 이미지를, 없으면 워드마크 색(남색·청록)으로 'LO' 모노그램을 그립니다.
    """

    NAVY = "#24165E"
    TEAL = "#5BC4C2"

    def __init__(self, size: int = 38, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        path = resource_path(os.path.join("asset", "brand_mark.png"))
        self._image = QPixmap(path) if os.path.exists(path) else None

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect())
        if self._image is not None and not self._image.isNull():
            clip = QPainterPath()
            clip.addRoundedRect(r, 10, 10)
            p.setClipPath(clip)
            p.drawPixmap(self.rect(), self._image)
            return
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.NAVY))
        p.drawRoundedRect(r, 10, 10)
        f = QFont(typography.family())
        f.setPixelSize(int(self.height() * 0.42))
        f.setWeight(QFont.Black)
        p.setFont(f)
        fm = QFontMetrics(f)
        lw, ow = fm.horizontalAdvance("L"), fm.horizontalAdvance("O")
        x = (self.width() - lw - ow + 1) / 2
        base = (self.height() + fm.ascent() - fm.descent()) / 2
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QPointF(x, base), "L")
        p.setPen(QColor(self.TEAL))
        p.drawText(QPointF(x + lw - 1, base), "O")


class Wordmark(QWidget):
    """'LYRICS / OVERLAY' 두 줄 워드마크 (로고 이미지와 같은 색 배치)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(130, 36)

    def paintEvent(self, event) -> None:
        t = theme_mod.active()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f1 = QFont(typography.family())
        f1.setPixelSize(17)
        f1.setWeight(QFont.Black)
        f1.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        p.setFont(f1)
        p.setPen(QColor("#FFFFFF" if t["name"] == "dark" else BrandMark.NAVY))
        p.drawText(QRectF(0, 0, self.width(), 19), Qt.AlignLeft | Qt.AlignBottom, "LYRICS")
        f2 = QFont(typography.family())
        f2.setPixelSize(11)
        f2.setWeight(QFont.Black)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 2.6)
        p.setFont(f2)
        p.setPen(QColor(BrandMark.TEAL if t["name"] == "dark" else "#2A9D9B"))
        p.drawText(QRectF(0, 21, self.width(), 14), Qt.AlignLeft | Qt.AlignTop, "OVERLAY")


class MiniNowPlaying(QWidget):
    """사이드바 아래 '지금 재생' 한 줄 (커버 + 제목/가수)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)
        self.title, self.artist, self.song_id = "", "", None
        self.hide()

    def set_song(self, title: str, artist: str, song_id=None) -> None:
        self.title, self.artist, self.song_id = title or "", artist or "", song_id
        self.setVisible(bool(self.title))
        self.setToolTip(f"{self.title} — {self.artist}" if self.title else "")
        self.update()

    def paintEvent(self, event) -> None:
        from gui.widgets.artwork import paint_art

        t = theme_mod.active()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QColor(t["glass_border"]))
        p.setBrush(QColor(t["card"]))
        p.drawRoundedRect(r, 10, 10)
        art = QRectF(10, (self.height() - 38) / 2, 38, 38)
        paint_art(p, art, self.title, self.artist, self.song_id, radius=5)
        left = int(art.right()) + 10
        w = self.width() - left - 10
        tf = typography.font(13, QFont.Bold)
        p.setFont(tf)
        p.setPen(QColor(t["text_primary"]))
        p.drawText(QRectF(left, 10, w, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(tf).elidedText(self.title, Qt.ElideRight, w))
        af = typography.font(12)
        p.setFont(af)
        p.setPen(QColor(t["text_secondary"]))
        p.drawText(QRectF(left, 29, w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(af).elidedText(self.artist, Qt.ElideRight, w))


class MainWindow(QMainWindow):
    """애플리케이션 메인 윈도우."""

    theme_changed = Signal(str)
    window_closed = Signal()
    quit_requested = Signal()  # 트레이 메뉴의 '종료'

    def __init__(self, stats: dict, app_config, initial_theme: str = "light"):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        # 노트북·고배율 화면에서도 화면을 넘지 않도록, 크기를 조절할 수 있게 하고
        # 처음 크기는 사용 가능한 화면 안에 맞춥니다.
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            # 최소 크기도 화면보다 크지 않게 (예: 1366×768 125% 배율이면 높이가 600 안팎)
            self.setMinimumSize(min(940, avail.width()), min(580, avail.height() - 40))
            w = min(1280, int(avail.width() * 0.92))
            h = min(760, int(avail.height() * 0.9))
            self.resize(max(w, self.minimumWidth()), max(h, self.minimumHeight()))
            self.move(avail.center() - self.rect().center())
        else:
            self.setMinimumSize(940, 580)
            self.resize(1280, 760)
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
        self.overlay.ensure_on_screen()  # 모니터 구성이 바뀌어 화면 밖에 있으면 데려옴
        self.overlay.edit_finished.connect(self.finish_overlay_edit)

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
        typography.load_fonts(resource_path(os.path.join("asset", "Font")))
        key = getattr(self.app_config, "ui_font", typography.DEFAULT_KEY)
        typography.set_font_key(key if typography.font_key_valid(key) else typography.DEFAULT_KEY)
        QApplication.setFont(typography.app_font())

    def set_ui_font(self, key: str) -> None:
        """설정에서 앱 글꼴을 바꾸면 바로 다시 그립니다."""
        if not typography.font_key_valid(key):
            return
        typography.set_font_key(key)
        if hasattr(self.app_config, "ui_font"):
            self.app_config.ui_font = key
        QApplication.setFont(typography.app_font())
        typography.refresh(self)
        self.apply_theme(self.theme_manager.current_theme)

    def _setup_ui(self) -> None:
        self.central_widget = GlassBackground()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 사이드바 (창 왼쪽에 붙은 단색 패널)
        self.sidebar = Card(shadow=False)
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(232)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 22, 14, 14)
        sidebar_layout.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.setContentsMargins(8, 0, 0, 0)
        brand.addWidget(BrandMark())
        brand.addWidget(Wordmark(), 0, Qt.AlignVCenter)
        brand.addStretch()
        sidebar_layout.addLayout(brand)
        sidebar_layout.addSpacing(26)

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
        self.mini_now = MiniNowPlaying()
        sidebar_layout.addWidget(self.mini_now)

        # 테마 전환 스위치
        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(12, 10, 6, 4)
        self.theme_glyph = label(icons.MOON, "IconGlyph", "font-size: 15px;")
        theme_row.addWidget(self.theme_glyph)
        theme_row.addSpacing(6)
        theme_row.addWidget(label("다크 모드", "Secondary", "font-weight: 600;"))
        theme_row.addStretch()
        self.theme_switch = ToggleSwitch()
        self.theme_switch.setAccessibleName("다크 모드")
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
        self.info_page = InfoPage(auto_check=getattr(self.app_config, "auto_update_check", True))
        self.pending_update = None  # core.updater.ReleaseInfo

        self.setting_page.settings_changed.connect(self.update_overlay)
        dp = self.dashboard_page
        dp.overlay_visible_toggled.connect(self._set_overlay_visible)
        dp.overlay_ghost_toggled.connect(self._set_overlay_ghost)
        dp.overlay_edit_requested.connect(self._toggle_overlay_edit)
        dp.overlay_reset_requested.connect(self.reset_overlay_position)
        dp.roi_requested.connect(self.setting_page._on_pick_roi)
        self.setting_page.overlay_edit_requested.connect(self.start_overlay_edit)
        self.setting_page.overlay_reset_requested.connect(self.reset_overlay_position)
        dp.update_notes_requested.connect(self._open_update_page)
        dp.update_skip_requested.connect(self._skip_update)
        dp.update_install_requested.connect(self._install_update)
        self.info_page.auto_check_toggled.connect(self._set_auto_update_check)
        self.info_page.install_requested.connect(self._install_update)
        self.setting_page.ui_font_changed.connect(self.set_ui_font)
        self.music_page.delete_requested.connect(self.delete_history)
        self.music_page.clear_requested.connect(self.clear_history)
        self.music_page.export_requested.connect(self.export_history)

        self.content_stack.addWidget(self.dashboard_page)  # index 0
        self.content_stack.addWidget(self.music_page)       # index 1
        self.content_stack.addWidget(self.stats_page)       # index 2
        self.content_stack.addWidget(self.setting_page)     # index 3
        self.content_stack.addWidget(self.info_page)        # index 4

        main_layout.addWidget(self.sidebar)
        self.content_stack.setContentsMargins(0, 18, 0, 12)
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
        tray.messageClicked.connect(self.show_from_tray)
        tray.show()
        self.tray = tray

    def _sync_tray_menu(self) -> None:
        self.tray_overlay_action.setChecked(self.config_manager.visible)
        self.tray_ghost_action.setChecked(self.config_manager.ghost_mode)

    def _tray_toggle_overlay(self) -> None:
        self._set_overlay_visible(not self.config_manager.visible)

    def _tray_toggle_ghost(self) -> None:
        self._set_overlay_ghost(not self.config_manager.ghost_mode)

    def _set_overlay_visible(self, visible: bool) -> None:
        self.config_manager.set_visible(visible)
        self.update_overlay()
        self.sync_controls()

    def _set_overlay_ghost(self, ghost: bool) -> None:
        if self.overlay.editing:
            self.finish_overlay_edit()
        self.config_manager.set_ghost_mode(ghost)
        self.update_overlay()
        self.sync_controls()

    def sync_controls(self) -> None:
        """대시보드·설정 화면의 스위치를 현재 설정에 맞춥니다."""
        self.dashboard_page.sync_overlay_controls(self.overlay.editing)
        self.setting_page.refresh_ui_from_config()

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

    # ------------------------------------------------------------------ #
    # 오버레이 위치·크기 조정 (편집 모드)
    # ------------------------------------------------------------------ #

    def start_overlay_edit(self) -> None:
        """한 번에 편집 모드로: 잠시 클릭을 받게 하고 드래그로 옮기거나 크기를 바꿀 수 있게.

        저장된 '클릭 통과'·'표시' 설정은 건드리지 않으므로 멜론 창 숨김 상태도 그대로입니다.
        """
        if self.overlay.editing:
            return
        self.overlay.ensure_on_screen()
        self.overlay.set_edit_mode(True)
        self.sync_controls()

    def finish_overlay_edit(self, apply: bool = True) -> None:
        """apply=False면 편집 전 위치·크기로 되돌립니다."""
        if not self.overlay.editing:
            return
        if not apply:
            self.overlay.cancel_edit_geometry()
        else:
            self.dashboard_page.mark_step(2)
        self.overlay.set_edit_mode(False)
        self.config_manager.save_now()
        self.sync_controls()

    def _toggle_overlay_edit(self) -> None:
        if self.overlay.editing:
            self.finish_overlay_edit(True)
        else:
            self.start_overlay_edit()

    def reset_overlay_position(self) -> None:
        if not self.config_manager.visible:
            self._set_overlay_visible(True)
        self.overlay.reset_position()
        self.sync_controls()

    # ------------------------------------------------------------------ #
    # 업데이트 알림
    # ------------------------------------------------------------------ #

    @staticmethod
    def _can_self_update() -> bool:
        return bool(getattr(sys, "frozen", False))  # 소스 실행은 git으로 업데이트

    def set_now_playing(self, title: str, artist: str, song_id=None) -> None:
        self.dashboard_page.set_now_playing(title, artist, song_id)
        self.mini_now.set_song(title, artist, song_id)

    def refresh_covers(self) -> None:
        """새 앨범 커버를 받았을 때 커버를 그리는 곳을 다시 그립니다."""
        self.dashboard_page.refresh_cover()
        self.mini_now.update()
        self.music_page.music_list.viewport().update()
        for lst in (self.stats_page.top_songs_list, self.stats_page.top_artists_list):
            lst.viewport().update()

    def show_update_available(self, info, manual: bool) -> None:
        self.pending_update = info
        can_install = self._can_self_update() and info.can_auto_update
        self.dashboard_page.show_update(info.version, can_install)
        self.info_page.set_update_status(f"새 버전 {info.version}이 있어요 (지금 버전: {APP_VERSION})")
        self.info_page.show_install(can_install)
        if not manual and self.tray is not None:
            self.tray.showMessage(
                "Lyrics Overlay 업데이트",
                f"새 버전 {info.version}이 나왔어요. 눌러서 열고 대시보드에서 업데이트하세요.",
                QSystemTrayIcon.Information, 6000,
            )

    def _set_auto_update_check(self, on: bool) -> None:
        if hasattr(self.app_config, "auto_update_check"):
            self.app_config.auto_update_check = on

    def _open_update_page(self) -> None:
        from PySide6.QtCore import QUrl  # type: ignore
        from PySide6.QtGui import QDesktopServices  # type: ignore
        from core.updater import RELEASES_PAGE

        url = self.pending_update.html_url if self.pending_update else RELEASES_PAGE
        QDesktopServices.openUrl(QUrl(url))

    def _skip_update(self) -> None:
        if self.pending_update and hasattr(self.app_config, "skipped_version"):
            self.app_config.skipped_version = self.pending_update.version
        self.dashboard_page.update_banner.hide()

    def _install_update(self) -> None:
        info = self.pending_update
        if info is None:
            return
        if not (self._can_self_update() and info.can_auto_update):
            self._open_update_page()
            return
        from gui.update_dialog import UpdateDialog

        if getattr(self, "_update_dialog", None) is not None and self._update_dialog.isVisible():
            self._update_dialog.raise_()
            return
        dlg = UpdateDialog(info, self)
        dlg.accepted.connect(lambda: self._apply_update(info, dlg.staged_path))
        self._update_dialog = dlg
        dlg.open()  # exec()와 달리 앱 메인 루프를 멈추지 않음

    def _apply_update(self, info, staged: str | None) -> None:
        from core import update_install

        if not staged:
            return
        try:
            update_install.hand_off(staged, info.exe_sha256, APP_VERSION)
        except Exception as e:
            QMessageBox.critical(self, "업데이트 실패", f"새 버전을 실행하지 못했어요. 지금 버전은 그대로예요.\n{e}")
            return
        # 새 exe가 이 프로그램이 완전히 끝나길 기다렸다가 교체하므로, 정상 종료 절차(멜론 창 복구·저장)를 밟습니다.
        self.request_quit()

    # ------------------------------------------------------------------ #
    # 감상 기록 관리 (삭제·내보내기)
    # ------------------------------------------------------------------ #

    def _commit_history(self, new_history: list[dict]) -> bool:
        """새 기록 목록을 먼저 파일에 저장하고, 성공했을 때만 메모리와 화면에 반영합니다.

        누적 감상 시간·가사 줄 수(total_*)는 기록을 지워도 그대로 둡니다.
        """
        from core.stats_manager import save_stats

        candidate = dict(self.persistent_stats)
        candidate["play_history"] = new_history
        if not save_stats(candidate, self.app_config.data_dir):
            QMessageBox.critical(self, "삭제 실패", "감상 기록 파일을 저장하지 못해 아무것도 지우지 않았어요.")
            return False
        self.persistent_stats["play_history"] = new_history
        self.music_page.set_history(new_history)
        dp = self.dashboard_page
        if hasattr(dp, "latest_session_stats"):
            dp.update_stats(dp.latest_session_stats, new_history)
        self.stats_page.update_stats(new_history, self.theme_manager.current_theme["name"])
        return True

    def delete_history(self, ids: list) -> None:
        history = self.persistent_stats.get("play_history", [])
        targets = set(ids)
        count = sum(1 for e in history if id(e) in targets)
        if not count:
            return
        reply = QMessageBox.question(
            self, "감상 기록 삭제",
            f"선택한 {count}곡의 감상 기록을 지울까요?\n지운 기록은 되돌릴 수 없어요. (누적 감상 시간은 그대로 유지)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        # 확인 창이 떠 있는 동안 새 곡이 추가됐을 수 있으니 최신 목록으로 다시 거릅니다.
        history = self.persistent_stats.get("play_history", [])
        self._commit_history([e for e in history if id(e) not in targets])

    def clear_history(self) -> None:
        history = self.persistent_stats.get("play_history", [])
        if not history:
            return
        reply = QMessageBox.question(
            self, "감상 기록 전체 삭제",
            f"지금 쓰고 있는 감상 기록 {len(history)}곡을 모두 지울까요?\n"
            "지운 기록은 되돌릴 수 없어요. 먼저 'CSV로 내보내기'로 보관해 둘 수 있어요.\n"
            "(누적 감상 시간과 가사 줄 수는 그대로 유지돼요)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._commit_history([])

    def export_history(self) -> None:
        import csv
        import time as _time

        history = list(self.persistent_stats.get("play_history", []))
        if not history:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "감상 기록 내보내기", f"감상기록_{_time.strftime('%Y%m%d')}.csv", "CSV 파일 (*.csv)"
        )
        if not path:
            return

        def cell(value) -> str:
            # 엑셀이 '=', '+', '-', '@'로 시작하는 값을 수식으로 실행하지 않도록 앞에 '를 붙입니다.
            text = str(value)
            return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text

        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["재생 시각", "제목", "가수", "재생 시간(초)", "가사 줄 수"])
                for e in history:
                    writer.writerow([
                        e.get("timestamp", ""), cell(e.get("title", "")), cell(e.get("artist", "")),
                        e.get("play_time_sec", 0), e.get("lines", 0),
                    ])
        except OSError as e:
            QMessageBox.critical(self, "내보내기 실패", f"파일을 저장하지 못했어요.\n{e}")
            return
        QMessageBox.information(self, "내보내기 완료", f"감상 기록 {len(history)}곡을 저장했어요.\n{path}")

    def update_overlay(self) -> None:
        """설정 변경 시 오버레이에 동기화합니다."""
        self.overlay.sync_with_config()
        if self.overlay.editing:
            self.overlay.set_edit_mode(True)  # 스타일이 바뀌어도 편집 표시 유지
        self.dashboard_page.sync_overlay_controls(self.overlay.editing)

    def switch_page(self, index: int) -> None:
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)
        # 통계 페이지 전환 시 데이터 업데이트
        if index == 3:
            # 오버레이를 드래그로 옮기거나 F9로 바꾼 값이 화면에 반영되게
            self.setting_page.refresh_ui_from_config()
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
