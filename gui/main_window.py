import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QFrame, QListWidget, QSlider, QCheckBox, QGroupBox,
                             QListWidgetItem, QGraphicsDropShadowEffect, QScrollArea,
                             QColorDialog, QFontDialog)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QRect, Signal
from PySide6.QtGui import QIcon, QColor, QFont, QPixmap, QFontDatabase

# Set up path for independent execution
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.roi_selector import ROISelector
from lyrics_overlay import LyricsOverlay, OverlayConfigManager

################################################################################
# UI CONFIGURATION - Edit these values to customize the appearance
################################################################################
class UIConfig:
    # ----- Sidebar Icons -----
    ICON_COLOR_DASHBOARD = "#F17979"
    ICON_COLOR_MUSIC = "#7EEFA4"
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


class SettingPage(QWidget):
    settings_changed = Signal()

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
        self.alpha_slider.setFixedHeight(20)
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
        color_out_vbox, self.btn_out_color = create_color_ctrl("아웃라인 색상", self.config.outline_color, "out")

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
        self.outline_slider.valueChanged.connect(self.on_outline_changed)
        
        outline_vbox.addLayout(outline_header)
        outline_vbox.addWidget(self.outline_slider)
        appearance_layout.addLayout(outline_vbox)
        
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
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def on_visible_toggled(self, checked):
        self.config.visible = checked
        self.settings_changed.emit()

    def on_ghost_toggled(self, checked):
        self.config.ghost_mode = checked
        self.settings_changed.emit()

    def on_alpha_changed(self, value):
        self.alpha_val_label.setText(str(value))
        self.config.update_background(opacity=value)
        self.settings_changed.emit()

    def on_outline_changed(self, value):
        self.outline_val_label.setText(str(value))
        self.config.update_text_style(outline_width=value)
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
            elif target == "out":
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

    def __init__(self, initial_theme="light"):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        self.setFixedSize(1280, 720)
        
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
        self.btn_settings = SidebarButton("설정  ⚙️", UIConfig.ICON_COLOR_SETTINGS)
        
        self.sidebar_layout.addWidget(self.btn_dashboard)
        self.sidebar_layout.addWidget(self.btn_music)
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
        self.setting_page = SettingPage(self.config_manager)
        
        self.setting_page.settings_changed.connect(self.update_overlay)
        
        self.content_stack.addWidget(self.dashboard_page)
        self.content_stack.addWidget(self.music_page)
        self.content_stack.addWidget(self.setting_page)
        
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_stack)

        self.nav_buttons = [self.btn_dashboard, self.btn_music, self.btn_settings]
        self.btn_dashboard.setChecked(True)
        
        self.btn_dashboard.clicked.connect(lambda: self.switch_page(0))
        self.btn_music.clicked.connect(lambda: self.switch_page(1))
        self.btn_settings.clicked.connect(lambda: self.switch_page(2))

    def update_overlay(self):
        self.overlay.sync_with_config()

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)

    def toggle_theme(self):
        new_theme = self.theme_manager.toggle_theme()
        self.apply_theme(new_theme)
        theme_name = "light" if new_theme == Theme.LIGHT else "dark"
        self.theme_changed.emit(theme_name)

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
