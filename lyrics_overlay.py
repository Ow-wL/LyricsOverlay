import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QColor
import win32gui
import win32con

class LyricsOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 배경을 투명하게 만들고 테두리 없는 윈도우로 설정
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 1. 메인 레이아웃 (여백 0으로 설정하여 꽉 채움)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 2. 배경과 테두리를 담당할 프레임 생성 (여기에 스타일을 적용해야 선이 안 생김)
        self.bg_frame = QFrame()
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 100); /* 검은색(0,0,0)에 투명도 100 */
                border-radius: 10px;
                border: none; /* 테두리 선 완전 제거 */
            }
        """)
        main_layout.addWidget(self.bg_frame)

        # 3. 프레임 내부의 레이아웃 (가사 라벨들이 들어갈 곳)
        self.frame_layout = QVBoxLayout(self.bg_frame)
        self.frame_layout.setSpacing(3) # 라벨 간 간격

        # 현재 가사 라벨
        self.curr_label = QLabel("현재 가사 대기 중...")
        self.curr_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
                background-color: transparent;
                border: none;
            }
        """)
        self.curr_label.setFont(QFont("Pretendard", 22))
        self.curr_label.setAlignment(Qt.AlignCenter)

        # 다음 가사 라벨
        self.next_label = QLabel("다음 가사...")
        self.next_label.setStyleSheet("""
            QLabel {
                color: #AAAAAA;
                background-color: transparent;
                border: none;
            }
        """)
        self.next_label.setFont(QFont("Pretendard", 16))
        self.next_label.setAlignment(Qt.AlignCenter)

        self.frame_layout.addWidget(self.curr_label)
        self.frame_layout.addWidget(self.next_label)

        self.setGeometry(460, 800, 666, 130)
        
        # 배치가 완료된 후 코드를 True로 바꾸거나, 핫키 이벤트를 추가해 전환하세요.
        # self.set_ghost_mode(False) # lyrics_main.py에서 제어하므로 제거

    def set_ghost_mode(self, enable):
        """클릭 통과만 설정. 투명도는 Qt가 관리하므로 건드리지 않음"""
        hwnd = self.winId()
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        
        if enable:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_TRANSPARENT)
        else:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style & ~win32con.WS_EX_TRANSPARENT)

    def update_lyrics(self, curr, nxt):
        """두 줄의 가사를 각각 업데이트"""
        if self.curr_label.text() != curr:
            self.curr_label.setText(curr)
        if self.next_label.text() != nxt:
            self.next_label.setText(nxt)
        self.curr_label.repaint()
        self.next_label.repaint()

    # 창 드래그 이동을 위한 마우스 이벤트 (조작 모드일 때만 작동)
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