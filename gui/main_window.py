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
from lyrics_overlay import LyricsOverlay

# ... (Theme, ThemeManager, Card, SidebarButton, DashboardPage, MusicListPage remain same)

class SettingPage(QWidget):
    settings_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        # Customization variables
        self.overlay_font = QFont("Pretendard", 24)
        self.text_color = QColor("#FFFFFF")
        self.bg_color = QColor(0, 0, 0)
        self.out_color = QColor(0, 0, 0)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        header = QLabel("오버레이 설정")
        header.setStyleSheet("font-size: 36px; font-weight: 900;")
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
        control_title.setStyleSheet("font-size: 18px; font-weight: 800;")
        control_desc = QLabel("가사 오버레이를 화면에 표시하거나 숨깁니다.")
        control_desc.setStyleSheet("font-size: 13px; color: #828282;")
        control_label_vbox.addWidget(control_title)
        control_label_vbox.addWidget(control_desc)
        
        self.overlay_switch = QCheckBox("OFF / ON")
        self.overlay_switch.setCursor(Qt.PointingHandCursor)
        self.overlay_switch.setStyleSheet("""
            QCheckBox { font-size: 16px; font-weight: 800; color: #7C4DFF; }
            QCheckBox::indicator { width: 40px; height: 40px; }
        """)
        self.overlay_switch.setChecked(True)
        self.overlay_switch.toggled.connect(self.emit_settings)
        
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
        app_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #828282;")
        appearance_layout.addWidget(app_title)

        # Font Selection
        font_hbox = QHBoxLayout()
        font_hbox.addWidget(QLabel("오버레이 글꼴"))
        self.btn_font = QPushButton("글꼴 변경  🔤")
        self.btn_font.setFixedSize(120, 35)
        self.btn_font.clicked.connect(self.pick_font)
        font_hbox.addStretch()
        font_hbox.addWidget(self.btn_font)
        appearance_layout.addLayout(font_hbox)
        
        # Transparency
        trans_vbox = QVBoxLayout()
        trans_vbox.setSpacing(12)
        trans_header_layout = QHBoxLayout()
        trans_label = QLabel("오버레이 불투명도")
        trans_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.alpha_val_label = QLabel("200")
        self.alpha_val_label.setStyleSheet("font-size: 16px; font-weight: 800; color: #7C4DFF;")
        trans_header_layout.addWidget(trans_label)
        trans_header_layout.addStretch()
        trans_header_layout.addWidget(self.alpha_val_label)
        
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(200)
        self.alpha_slider.setFixedHeight(20)
        self.alpha_slider.valueChanged.connect(self.on_alpha_changed)
        
        trans_vbox.addLayout(trans_header_layout)
        trans_vbox.addWidget(self.alpha_slider)
        appearance_layout.addLayout(trans_vbox)

        # Color Settings
        color_grid = QHBoxLayout()
        
        # Text Color
        text_color_vbox = QVBoxLayout()
        text_color_vbox.addWidget(QLabel("글씨 색상"))
        self.btn_text_color = QPushButton()
        self.btn_text_color.setFixedSize(60, 30)
        self.btn_text_color.setStyleSheet(f"background-color: {self.text_color.name()}; border: 1px solid #E0E0E0;")
        self.btn_text_color.clicked.connect(lambda: self.pick_color("text"))
        text_color_vbox.addWidget(self.btn_text_color)
        
        # Background Color
        bg_color_vbox = QVBoxLayout()
        bg_color_vbox.addWidget(QLabel("배경 색상"))
        self.btn_bg_color = QPushButton()
        self.btn_bg_color.setFixedSize(60, 30)
        self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color.name()}; border: 1px solid #E0E0E0;")
        self.btn_bg_color.clicked.connect(lambda: self.pick_color("bg"))
        bg_color_vbox.addWidget(self.btn_bg_color)

        # Outline Color
        out_color_vbox = QVBoxLayout()
        out_color_vbox.addWidget(QLabel("아웃라인 색상"))
        self.btn_out_color = QPushButton()
        self.btn_out_color.setFixedSize(60, 30)
        self.btn_out_color.setStyleSheet(f"background-color: {self.out_color.name()}; border: 1px solid #E0E0E0;")
        self.btn_out_color.clicked.connect(lambda: self.pick_color("out"))
        out_color_vbox.addWidget(self.btn_out_color)

        color_grid.addLayout(text_color_vbox)
        color_grid.addSpacing(20)
        color_grid.addLayout(bg_color_vbox)
        color_grid.addSpacing(20)
        color_grid.addLayout(out_color_vbox)
        color_grid.addStretch()
        appearance_layout.addLayout(color_grid)

        # Outline Thickness
        outline_vbox = QVBoxLayout()
        outline_vbox.setSpacing(12)
        outline_header = QHBoxLayout()
        outline_header.addWidget(QLabel("아웃라인 두께"))
        self.outline_val_label = QLabel("2")
        self.outline_val_label.setStyleSheet("font-weight: 800; color: #7C4DFF;")
        outline_header.addStretch()
        outline_header.addWidget(self.outline_val_label)
        
        self.outline_slider = QSlider(Qt.Horizontal)
        self.outline_slider.setRange(0, 10)
        self.outline_slider.setValue(2)
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
        int_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #828282;")
        interaction_layout.addWidget(int_title)
        
        # Ghost Mode
        ghost_layout = QHBoxLayout()
        ghost_label_vbox = QVBoxLayout()
        ghost_title = QLabel("고스트 모드")
        ghost_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        ghost_desc = QLabel("오버레이가 마우스 클릭을 통과하도록 설정합니다.")
        ghost_desc.setStyleSheet("font-size: 13px; color: #828282;")
        ghost_label_vbox.addWidget(ghost_title)
        ghost_label_vbox.addWidget(ghost_desc)
        
        self.ghost_check = QCheckBox()
        self.ghost_check.setCursor(Qt.PointingHandCursor)
        self.ghost_check.setChecked(True)
        self.ghost_check.setStyleSheet("QCheckBox::indicator { width: 24px; height: 24px; }")
        self.ghost_check.toggled.connect(self.emit_settings)
        
        ghost_layout.addLayout(ghost_label_vbox)
        ghost_layout.addStretch()
        ghost_layout.addWidget(self.ghost_check)
        interaction_layout.addLayout(ghost_layout)
        
        # ROI Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #E0E0E0;")
        interaction_layout.addWidget(line)
        
        # ROI Button (Commented out as requested)
        roi_vbox = QVBoxLayout()
        roi_vbox.setSpacing(12)
        roi_title = QLabel("영역 설정 (비활성화됨)")
        roi_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #AAAAAA;")
        roi_desc = QLabel("가사가 출력되는 멜론 창의 영역을 직접 선택합니다.")
        roi_desc.setStyleSheet("font-size: 13px; color: #AAAAAA;")
        
        self.roi_btn = QPushButton("가사 인식 영역 설정 (ROI)  🎯")
        self.roi_btn.setEnabled(False) # Disable for now
        self.roi_btn.setMinimumHeight(55)
        self.roi_btn.setStyleSheet("background-color: #EEEEEE; color: #AAAAAA; border-radius: 10px;")
        # self.roi_btn.clicked.connect(self.start_roi_selection)
        
        roi_vbox.addWidget(roi_title)
        roi_vbox.addWidget(roi_desc)
        roi_vbox.addWidget(self.roi_btn)
        interaction_layout.addLayout(roi_vbox)
        
        scroll_layout.addWidget(interaction_card)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def on_alpha_changed(self, value):
        self.alpha_val_label.setText(str(value))
        self.emit_settings()

    def on_outline_changed(self, value):
        self.outline_val_label.setText(str(value))
        self.emit_settings()

    def pick_color(self, target):
        color = QColorDialog.getColor()
        if color.isValid():
            if target == "text":
                self.text_color = color
                self.btn_text_color.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #E0E0E0;")
            elif target == "bg":
                self.bg_color = color
                self.btn_bg_color.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #E0E0E0;")
            elif target == "out":
                self.out_color = color
                self.btn_out_color.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #E0E0E0;")
            self.emit_settings()

    def pick_font(self):
        ok, font = QFontDialog.getFont(self.overlay_font, self)
        if ok:
            self.overlay_font = font
            self.emit_settings()

    def get_settings(self):
        bg_with_alpha = QColor(self.bg_color)
        bg_with_alpha.setAlpha(self.alpha_slider.value())
        return {
            'visible': self.overlay_switch.isChecked(),
            'font': self.overlay_font,
            'text_color': self.text_color,
            'bg_color': bg_with_alpha,
            'out_color': self.out_color,
            'out_width': self.outline_slider.value(),
            'ghost': self.ghost_check.isChecked()
        }

    def emit_settings(self):
        self.settings_changed.emit(self.get_settings())

    def start_roi_selection(self):
        # self.selector = ROISelector()
        # self.selector.show()
        pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lyrics Overlay")
        self.setFixedSize(1280, 720)
        
        # Set Window Icon
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "asset", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self.theme_manager = ThemeManager()
        self.overlay = LyricsOverlay()
        
        self.load_fonts()
        self.setup_ui()
        self.apply_theme(self.theme_manager.current_theme)
        
        # Initialize overlay settings
        self.update_overlay(self.setting_page.get_settings())
        self.overlay.show()

    def load_fonts(self):
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "asset", "Font")
        if os.path.exists(font_dir):
            for font_file in os.listdir(font_dir):
                if font_file.endswith(".ttf"):
                    QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
        
        self.default_font = QFont("Pretendard", 12)
        QApplication.setFont(self.default_font)

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(16, 24, 16, 24)
        self.sidebar_layout.setSpacing(8)
        
        menu_label = QLabel("메뉴")
        menu_label.setObjectName("SidebarMenuLabel")
        self.sidebar_layout.addWidget(menu_label)
        
        self.btn_dashboard = SidebarButton("대시보드  🏠", "#F17979")
        self.btn_music = SidebarButton("가사 목록  🎵", "#7EEFA4")
        self.btn_settings = SidebarButton("설정  ⚙️", "#75EDF1")
        
        self.sidebar_layout.addWidget(self.btn_dashboard)
        self.sidebar_layout.addWidget(self.btn_music)
        self.sidebar_layout.addWidget(self.btn_settings)
        
        self.sidebar_layout.addStretch()
        
        # Theme Toggle Button
        self.btn_theme = QPushButton("🌓  테마 전환")
        self.btn_theme.setObjectName("ThemeButton")
        self.btn_theme.setMinimumHeight(50)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.sidebar_layout.addWidget(self.btn_theme)
        
        # Content Area
        self.content_stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.music_page = MusicListPage()
        self.setting_page = SettingPage()
        
        # Connect settings signal
        self.setting_page.settings_changed.connect(self.update_overlay)
        
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

    def update_overlay(self, settings):
        self.overlay.apply_settings(settings)

    def switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)

    def toggle_theme(self):
        new_theme = self.theme_manager.toggle_theme()
        self.apply_theme(new_theme)

    def apply_theme(self, theme):
        is_light = theme == Theme.LIGHT
        
        # Sidebar Colors
        if is_light:
            sb_normal_text = "#14043F"
            sb_active_bg = "#001D52"
            sb_active_text = "#FFFFFF"
            sb_hover_bg = "#E9ECEF"
        else:
            sb_normal_text = "#FFFFFF"
            sb_active_bg = "#00995E"
            sb_active_text = "#FFFFFF"
            sb_hover_bg = "#2C2C2C"
        
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
                font-size: 28px;
                font-family: 'Pretendard SemiBold', 'Pretendard';
                font-weight: 800;
                margin-bottom: 15px;
                padding-left: 8px;
                color: {theme["text_primary"]};
            }}
            QFrame#Card {{
                background-color: {theme["bg_card"]};
                border-radius: 12px;
                border: 1px solid {theme["border"]};
            }}
            QGroupBox {{
                background-color: {theme["bg_card"]};
                border: 1px solid {theme["border"]};
                border-radius: 12px;
                margin-top: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                color: {theme["text_primary"]};
            }}
            QPushButton {{
                background-color: {theme["accent"]};
                color: white;
                border-radius: 10px;
                font-weight: 600;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {theme["accent_hover"]};
            }}
            SidebarButton {{
                background-color: transparent;
                border: none;
                border-radius: 10px;
                text-align: left;
                padding-left: 55px;
                font-family: 'Pretendard SemiBold', 'Pretendard';
                font-weight: 600;
                font-size: 18px;
                color: {sb_normal_text};
            }}
            SidebarButton:hover {{
                background-color: {sb_hover_bg};
            }}
            SidebarButton:checked {{
                background-color: {sb_active_bg};
                color: {sb_active_text};
                font-family: 'Pretendard SemiBold', 'Pretendard';
                font-weight: 800;
            }}
            QListWidget {{
                color: {theme["text_primary"]};
                background-color: transparent;
                border: none;
                font-size: 16px;
            }}
            QLabel#PageHeader {{
                color: {theme["text_primary"]};
                margin-bottom: 10px;
            }}
            QCheckBox, QSlider {{
                color: {theme["text_primary"]};
                background-color: transparent;
            }}
            QLabel {{
                color: {theme["text_primary"]};
                background-color: transparent;
            }}
        """
        self.central_widget.setStyleSheet(style)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
