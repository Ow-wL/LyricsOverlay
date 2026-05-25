import sys
import json
import os
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QBrush
import win32gui
import win32con

class OverlayConfigManager:
    """오버레이 스타일 및 설정을 관리하는 매니저 클래스"""
    
    def __init__(self, config_path="overlay_settings.json", styles_path="overlay_styles.json"):
        self.config_path = config_path
        self.styles_path = styles_path
        self.PRESET_STYLES = {}
        self.custom_presets = {} # 사용자가 저장한 프리셋
        
        # 기본 스타일 로드
        self.load_styles()
        
        # 기본 스타일 설정
        self.bg_color = QColor(0, 0, 0, 100)      # 배경색 (RGBA)
        self.text_color = QColor(255, 255, 255)  # 글자색
        self.outline_color = QColor(0, 0, 0)     # 아웃라인 색
        self.outline_width = 2                   # 아웃라인 두께
        self.font_family = "Pretendard"          # 폰트 종류
        self.font_size = 22                      # 폰트 크기
        self.ghost_mode = True                   # 클릭 통과 모드
        self.visible = True                      # 표시 여부
        self.move_enabled = False                # 위치 이동 가능 여부
        self.resize_enabled = False              # 크기 조절 가능 여부 설정
        self.hotkey_ghost = "F9"                 # 고스트 모드 토글 단축키
        self.hotkey_quit = "Shift+Q"             # 프로그램 종료 단축키
        self.x = 460                             # 기본 X 위치
        self.y = 800                             # 기본 Y 위치
        self.width = 800                         # 기본 너비
        self.height = 150                        # 기본 높이
        
        # 파일에서 설정 로드
        self.load_from_file()

    def load_styles(self):
        """별도의 파일에서 프리셋 스타일을 로드합니다."""
        if os.path.exists(self.styles_path):
            try:
                with open(self.styles_path, "r", encoding="utf-8") as f:
                    self.PRESET_STYLES = json.load(f)
            except Exception as e:
                print(f"Failed to load styles from {self.styles_path}: {e}")
                self.PRESET_STYLES = {}
        else:
            # 파일이 없을 경우 기본값 설정
            self.PRESET_STYLES = {
                "기본 (반투명 검정)": {
                    "bg_color": "#000000", "bg_alpha": 100, "text_color": "#FFFFFF",
                    "outline_color": "#000000", "outline_width": 2
                }
            }
            self.save_styles()

    def save_styles(self):
        """현재 프리셋 스타일을 파일에 저장합니다."""
        try:
            with open(self.styles_path, "w", encoding="utf-8") as f:
                json.dump(self.PRESET_STYLES, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save styles to {self.styles_path}: {e}")

    def export_styles(self, export_path):
        """프리셋 스타일과 커스텀 프리셋을 별도의 파일로 내보냅니다."""
        try:
            export_data = {
                "system_presets": self.PRESET_STYLES,
                "custom_presets": self.custom_presets
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to export styles: {e}")
            return False

    def import_styles(self, import_path):
        """파일에서 프리셋 스타일을 가져옵니다."""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
            
            # 형식이 통합된 내보내기 파일인 경우
            if "system_presets" in import_data or "custom_presets" in import_data:
                if "system_presets" in import_data:
                    self.PRESET_STYLES.update(import_data["system_presets"])
                if "custom_presets" in import_data:
                    self.custom_presets.update(import_data["custom_presets"])
            else:
                # 단순 스타일 그리드 파일인 경우
                self.PRESET_STYLES.update(import_data)
            
            self.save_styles()
            self.save_to_file()
            return True
        except Exception as e:
            print(f"Failed to import styles: {e}")
            return False

    def apply_preset(self, preset_data):
        """프리셋 데이터를 적용합니다."""
        if "bg_color" in preset_data:
            self.bg_color = QColor(preset_data["bg_color"])
            if "bg_alpha" in preset_data:
                self.bg_color.setAlpha(preset_data["bg_alpha"])
        
        if "text_color" in preset_data:
            self.text_color = QColor(preset_data["text_color"])
        
        if "outline_color" in preset_data:
            self.outline_color = QColor(preset_data["outline_color"])
        
        if "outline_width" in preset_data:
            self.outline_width = preset_data["outline_width"]

        if "font_family" in preset_data:
            self.font_family = preset_data["font_family"]
        
        if "font_size" in preset_data:
            self.font_size = preset_data["font_size"]
        
        self.save_to_file()

    def save_custom_preset(self, name):
        """현재 스타일을 사용자 프리셋으로 저장합니다."""
        self.custom_presets[name] = {
            "bg_color": self.bg_color.name(),
            "bg_alpha": self.bg_color.alpha(),
            "text_color": self.text_color.name(),
            "outline_color": self.outline_color.name(),
            "outline_width": self.outline_width,
            "font_family": self.font_family,
            "font_size": self.font_size
        }
        self.save_to_file()

    def delete_custom_preset(self, name):
        """사용자 프리셋을 삭제합니다."""
        if name in self.custom_presets:
            del self.custom_presets[name]
            self.save_to_file()

    def get_settings(self):
        """현재 설정을 dict 형태로 반환 (LyricsOverlay.apply_settings 호환용)"""
        return {
            'bg_color': self.bg_color,
            'text_color': self.text_color,
            'out_color': self.outline_color,
            'out_width': self.outline_width,
            'font': QFont(self.font_family, self.font_size),
            'ghost': self.ghost_mode,
            'visible': self.visible,
            'move_enabled': self.move_enabled,
            'resize_enabled': self.resize_enabled,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height
        }

    def update_background(self, color=None, opacity=None):
        """배경색 및 투명도 업데이트 (opacity: 0~255)"""
        if color:
            new_color = QColor(color)
            if opacity is not None:
                new_color.setAlpha(opacity)
            else:
                new_color.setAlpha(self.bg_color.alpha())
            self.bg_color = new_color
        elif opacity is not None:
            self.bg_color.setAlpha(opacity)
        self.save_to_file()

    def update_text_style(self, color=None, outline_color=None, outline_width=None):
        """글자 스타일 업데이트"""
        if color: self.text_color = QColor(color)
        if outline_color: self.outline_color = QColor(outline_color)
        if outline_width is not None: self.outline_width = outline_width
        self.save_to_file()

    def update_font(self, family=None, size=None):
        """폰트 업데이트"""
        if family: self.font_family = family
        if size is not None: self.font_size = size
        self.save_to_file()

    def update_position(self, x, y):
        """위치 정보 업데이트"""
        self.x = x
        self.y = y
        self.save_to_file()

    def update_size(self, width, height):
        """크기 정보 업데이트"""
        self.width = width
        self.height = height
        self.save_to_file()

    def set_visible(self, visible):
        self.visible = visible
        self.save_to_file()

    def set_ghost_mode(self, ghost):
        self.ghost_mode = ghost
        self.save_to_file()

    def set_move_enabled(self, enabled):
        self.move_enabled = enabled
        self.save_to_file()

    def set_resize_enabled(self, enabled):
        self.resize_enabled = enabled
        self.save_to_file()

    def update_hotkey_ghost(self, hotkey):
        self.hotkey_ghost = hotkey
        self.save_to_file()

    def update_hotkey_quit(self, hotkey):
        self.hotkey_quit = hotkey
        self.save_to_file()

    def save_to_file(self):
        """설정을 JSON 파일로 저장"""
        try:
            data = {
                "bg_color": self.bg_color.name(),
                "bg_alpha": self.bg_color.alpha(),
                "text_color": self.text_color.name(),
                "outline_color": self.outline_color.name(),
                "outline_width": self.outline_width,
                "font_family": self.font_family,
                "font_size": self.font_size,
                "ghost_mode": self.ghost_mode,
                "visible": self.visible,
                "move_enabled": self.move_enabled,
                "resize_enabled": self.resize_enabled,
                "hotkey_ghost": self.hotkey_ghost,
                "hotkey_quit": self.hotkey_quit,
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
                "custom_presets": self.custom_presets
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_from_file(self):
        """JSON 파일에서 설정 로드"""
        if not os.path.exists(self.config_path):
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "bg_color" in data:
                self.bg_color = QColor(data["bg_color"])
                if "bg_alpha" in data:
                    self.bg_color.setAlpha(data["bg_alpha"])
            
            if "text_color" in data:
                self.text_color = QColor(data["text_color"])
            
            if "outline_color" in data:
                self.outline_color = QColor(data["outline_color"])
            
            self.outline_width = data.get("outline_width", self.outline_width)
            self.font_family = data.get("font_family", self.font_family)
            self.font_size = data.get("font_size", self.font_size)
            self.ghost_mode = data.get("ghost_mode", self.ghost_mode)
            self.visible = data.get("visible", self.visible)
            self.move_enabled = data.get("move_enabled", self.move_enabled)
            self.resize_enabled = data.get("resize_enabled", self.resize_enabled)
            self.hotkey_ghost = data.get("hotkey_ghost", self.hotkey_ghost)
            self.hotkey_quit = data.get("hotkey_quit", self.hotkey_quit)
            self.x = data.get("x", self.x)
            self.y = data.get("y", self.y)
            self.width = data.get("width", self.width)
            self.height = data.get("height", self.height)
            self.custom_presets = data.get("custom_presets", {})
        except Exception as e:
            print(f"Failed to load settings: {e}")

class OutlinedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.outline_color = QColor(0, 0, 0)
        self.outline_width = 2
        self.text_color = QColor(255, 255, 255)
        self.set_style(QFont("Pretendard", 22), self.text_color, self.outline_color, self.outline_width)

    def set_style(self, font, text_color, outline_color, outline_width):
        self.setFont(font)
        self.text_color = QColor(text_color)
        self.outline_color = QColor(outline_color)
        self.outline_width = outline_width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        
        # 텍스트 정렬 계산
        font_metrics = self.fontMetrics()
        text_rect = font_metrics.boundingRect(self.text())
        
        x = 0
        if self.alignment() & Qt.AlignHCenter:
            x = (self.width() - text_rect.width()) / 2
        elif self.alignment() & Qt.AlignRight:
            x = self.width() - text_rect.width()
            
        y = (self.height() + font_metrics.ascent() - font_metrics.descent()) / 2

        path.addText(x, y, self.font(), self.text())

        # 아웃라인 그리기
        if self.outline_width > 0:
            pen = QPen(self.outline_color, self.outline_width * 2)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

        # 텍스트 채우기
        painter.fillPath(path, QBrush(self.text_color))

class LyricsOverlay(QWidget):
    def __init__(self, config=None):
        super().__init__()
        # 외부 매니저를 주입받거나 새로 생성
        self.config = config if config else OverlayConfigManager()
        self.bg_color = self.config.bg_color
        self.move_enabled = self.config.move_enabled
        self.resize_enabled = self.config.resize_enabled
        self.init_ui()
        self.sync_with_config()

    def set_move_enabled(self, enabled):
        """위치 조절 가능 여부 설정"""
        self.move_enabled = enabled
        if not enabled and not self.resize_enabled:
            self.setCursor(Qt.ArrowCursor)

    def set_resize_enabled(self, enabled):
        """크기 조절 가능 여부 설정"""
        self.resize_enabled = enabled
        if not enabled and not self.move_enabled:
            self.setCursor(Qt.ArrowCursor)

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("LyricsBgFrame")
        self.update_bg_style()
        main_layout.addWidget(self.bg_frame)

        self.frame_layout = QVBoxLayout(self.bg_frame)
        self.frame_layout.setSpacing(5)

        self.curr_label = OutlinedLabel("현재 가사 대기 중...")
        self.curr_label.setAlignment(Qt.AlignCenter)
        self.curr_label.setStyleSheet("background: transparent;")

        self.next_label = OutlinedLabel("다음 가사...")
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setStyleSheet("background: transparent;")

        self.frame_layout.addWidget(self.curr_label)
        self.frame_layout.addWidget(self.next_label)

        # 저장된 위치 및 크기 설정
        self.setGeometry(self.config.x, self.config.y, self.config.width, self.config.height)
        
        self.resizing = False
        self.resize_margin = 15

    def sync_with_config(self):
        """매니저의 현재 설정을 UI에 동기화"""
        self.apply_settings(self.config.get_settings())

    def update_bg_style(self):
        self.bg_frame.setStyleSheet(f"""
            QFrame#LyricsBgFrame {{
                background-color: rgba({self.bg_color.red()}, {self.bg_color.green()}, {self.bg_color.blue()}, {self.bg_color.alpha()});
                border-radius: 15px;
                border: none;
            }}
        """)

    def apply_settings(self, settings):
        """
        settings: dict with keys:
        - font: QFont
        - text_color: QColor
        - bg_color: QColor (including alpha)
        - out_color: QColor
        - out_width: int
        - visible: bool
        - ghost: bool
        - x: int
        - y: int
        - width: int
        - height: int
        - move_enabled: bool
        - resize_enabled: bool
        """
        if not settings.get('visible', True):
            self.hide()
            return
        else:
            self.show()

        if 'bg_color' in settings:
            self.bg_color = settings['bg_color']
            self.update_bg_style()

        # 위치 및 크기 복원
        x = settings.get('x', self.x())
        y = settings.get('y', self.y())
        w = settings.get('width', self.width())
        h = settings.get('height', self.height())
        self.setGeometry(x, y, w, h)

        font = settings.get('font', self.curr_label.font())
        text_color = settings.get('text_color', self.curr_label.text_color)
        out_color = settings.get('out_color', self.curr_label.outline_color)
        out_width = settings.get('out_width', self.curr_label.outline_width)

        self.curr_label.set_style(font, text_color, out_color, out_width)
        
        # 다음 가사 스타일 (현재 가사보다 약간 작고 투명하게)
        next_font = QFont(font)
        next_font.setPointSize(max(8, font.pointSize() - 6))
        self.next_label.set_style(
            next_font, 
            QColor(text_color.red(), text_color.green(), text_color.blue(), 180), 
            out_color, 
            max(0, out_width - 1)
        )

        if 'ghost' in settings:
            self.set_ghost_mode(settings['ghost'])
            
        if 'move_enabled' in settings:
            self.move_enabled = settings['move_enabled']
        if 'resize_enabled' in settings:
            self.resize_enabled = settings['resize_enabled']

    def set_ghost_mode(self, enable):
        hwnd = self.winId()
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if enable:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_TRANSPARENT)
        else:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style & ~win32con.WS_EX_TRANSPARENT)

    def update_lyrics(self, curr, nxt):
        if self.curr_label.text() != curr:
            self.curr_label.setText(curr)
        if self.next_label.text() != nxt:
            self.next_label.setText(nxt)
        self.update()

    def mousePressEvent(self, event):
        if not self.move_enabled and not self.resize_enabled:
            return
            
        if event.button() == Qt.LeftButton:
            # 우측 하단 모서리 클릭 시 리사이즈 모드 (리사이즈가 활성화된 경우만)
            if self.resize_enabled and \
               event.pos().x() > self.width() - self.resize_margin and \
               event.pos().y() > self.height() - self.resize_margin:
                self.resizing = True
            elif self.move_enabled:
                self.resizing = False
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if not self.move_enabled and not self.resize_enabled:
            return

        # 마우스 커서 모양 변경 (리사이즈 영역) - 리사이즈가 활성화된 경우만
        if self.resize_enabled and \
           event.pos().x() > self.width() - self.resize_margin and \
           event.pos().y() > self.height() - self.resize_margin:
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if event.buttons() == Qt.LeftButton:
            if self.resizing and self.resize_enabled:
                # 크기 조절
                new_width = max(200, event.pos().x())
                new_height = max(80, event.pos().y())
                self.resize(new_width, new_height)
                self.config.update_size(new_width, new_height)
            elif not self.resizing and self.move_enabled:
                # 위치 이동
                delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
                new_x = self.x() + delta.x()
                new_y = self.y() + delta.y()
                self.move(new_x, new_y)
                self.old_pos = event.globalPosition().toPoint()
                self.config.update_position(new_x, new_y)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 매니저 사용 예시
    config = OverlayConfigManager()
    config.update_background("#000000", 150) # 검은색 배경, 투명도 150
    config.update_text_style(color="#00FF00", outline_color="#000000", outline_width=3) # 초록색 글자, 검은 아웃라인
    
    overlay = LyricsOverlay(config)
    overlay.show()
    sys.exit(app.exec())
