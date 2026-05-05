import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QBrush
import win32gui
import win32con

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
        
        # Calculate alignment
        font_metrics = self.fontMetrics()
        text_rect = font_metrics.boundingRect(self.text())
        
        x = 0
        if self.alignment() & Qt.AlignHCenter:
            x = (self.width() - text_rect.width()) / 2
        elif self.alignment() & Qt.AlignRight:
            x = self.width() - text_rect.width()
            
        y = (self.height() + font_metrics.ascent() - font_metrics.descent()) / 2

        path.addText(x, y, self.font(), self.text())

        # Draw outline
        if self.outline_width > 0:
            pen = QPen(self.outline_color, self.outline_width * 2)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

        # Draw text
        painter.fillPath(path, QBrush(self.text_color))

class LyricsOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.bg_color = QColor(0, 0, 0, 100)
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

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
        self.next_label.set_style(QFont("Pretendard", 16), QColor("#AAAAAA"), QColor(0, 0, 0), 1)

        self.frame_layout.addWidget(self.curr_label)
        self.frame_layout.addWidget(self.next_label)

        self.setGeometry(460, 800, 800, 150)

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
        """
        if not settings.get('visible', True):
            self.hide()
            return
        else:
            self.show()

        if 'bg_color' in settings:
            self.bg_color = settings['bg_color']
            self.update_bg_style()

        font = settings.get('font', self.curr_label.font())
        text_color = settings.get('text_color', self.curr_label.text_color)
        out_color = settings.get('out_color', self.curr_label.outline_color)
        out_width = settings.get('out_width', self.curr_label.outline_width)

        self.curr_label.set_style(font, text_color, out_color, out_width)
        
        # Next label style is slightly dimmed version of curr label
        next_font = QFont(font)
        next_font.setPointSize(max(8, font.pointSize() - 6))
        self.next_label.set_style(next_font, QColor(text_color.red(), text_color.green(), text_color.blue(), 180), out_color, max(0, out_width - 1))

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
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = LyricsOverlay()
    overlay.show()
    sys.exit(app.exec())
