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
    def __init__(self, config_path="overlay_settings.json"):
        self.config_path = config_path
        # 기본 스타일 설정
        self.bg_color = QColor(0, 0, 0, 100)      # 배경색 (RGBA)
        self.text_color = QColor(255, 255, 255)  # 글자색
        self.outline_color = QColor(0, 0, 0)     # 아웃라인 색
        self.outline_width = 2                   # 아웃라인 두께
        self.font_family = "Pretendard"          # 폰트 종류
        self.font_size = 22                      # 폰트 크기
        self.ghost_mode = True                   # 클릭 통과 모드
        self.visible = True                      # 표시 여부
        self.x = 460                             # 기본 X 위치
        self.y = 800                             # 기본 Y 위치
        self.width = 800                         # 기본 너비
        self.height = 150                        # 기본 높이
        
        # 파일에서 설정 로드
        self.load_from_file()

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
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
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
            self.x = data.get("x", self.x)
            self.y = data.get("y", self.y)
            self.width = data.get("width", self.width)
            self.height = data.get("height", self.height)
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
        self.init_ui()
        self.sync_with_config()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.bg_frame = QFrame()
        self.update_bg_style()
        main_layout.addWidget(self.bg_frame)

        self.frame_layout = QVBoxLayout(self.bg_frame)
        self.frame_layout.setSpacing(5)

        self.curr_label = OutlinedLabel("현재 가사 대기 중...")
        self.curr_label.setAlignment(Qt.AlignCenter)

        self.next_label = OutlinedLabel("다음 가사...")
        self.next_label.setAlignment(Qt.AlignCenter)

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
            QFrame {{
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
        if event.button() == Qt.LeftButton:
            # 우측 하단 모서리 클릭 시 리사이즈 모드
            if event.pos().x() > self.width() - self.resize_margin and \
               event.pos().y() > self.height() - self.resize_margin:
                self.resizing = True
            else:
                self.resizing = False
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        # 마우스 커서 모양 변경 (리사이즈 영역)
        if event.pos().x() > self.width() - self.resize_margin and \
           event.pos().y() > self.height() - self.resize_margin:
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if event.buttons() == Qt.LeftButton:
            if self.resizing:
                # 크기 조절
                new_width = max(200, event.pos().x())
                new_height = max(80, event.pos().y())
                self.resize(new_width, new_height)
                self.config.update_size(new_width, new_height)
            else:
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
