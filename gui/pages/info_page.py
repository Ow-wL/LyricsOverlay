"""프로그램 및 개발자 정보 페이지."""

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget  # type: ignore

from core.version import APP_VERSION
from gui import icons
from gui.widgets.card import Card
from gui.widgets.glass import ToggleSwitch, divider, icon_chip, label, page_header


class InfoPage(QWidget):
    """프로그램 정보 및 개발자 정보, 업데이트 확인을 표시하는 페이지."""

    check_update_requested = Signal()
    auto_check_toggled = Signal(bool)

    def __init__(self, auto_check: bool = True):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 14, 28, 6)
        layout.setSpacing(22)

        layout.addWidget(page_header("정보", "프로그램과 개발자 정보"))

        info_card = Card()
        info_vbox = QVBoxLayout(info_card)
        info_vbox.setContentsMargins(30, 28, 30, 28)
        info_vbox.setSpacing(20)

        # 앱 이름 및 버전
        app_row = QHBoxLayout()
        app_row.setSpacing(16)
        app_row.addWidget(icon_chip(icons.MUSIC, 52))
        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name_col.addWidget(label("Lyrics Overlay", "", "font-size: 24px; font-weight: 800; letter-spacing: -0.5px;"))
        name_col.addWidget(label(f"Version {APP_VERSION}", "Secondary", "font-weight: 600;"))
        app_row.addLayout(name_col)
        app_row.addStretch()
        info_vbox.addLayout(app_row)

        info_vbox.addWidget(label(
            "멜론에서 재생 중인 가사를 화면에서 읽어 와, 어떤 작업을 하든 화면 위에 띄워 주는 가사 오버레이입니다.",
            "Secondary",
        ))
        info_vbox.addWidget(divider())

        info_vbox.addWidget(label("개발자", "SectionLabel"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(12)
        rows = [
            ("이름", "이주형 (Ow-wL)"),
            ("이메일", "ganno1208@naver.com"),
            ("GitHub", "https://github.com/Ow-wL"),
        ]
        for i, (k, v) in enumerate(rows):
            grid.addWidget(label(k, "Tertiary", "font-weight: 600;"), i, 0)
            value = label(v, "", "font-weight: 600;")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(value, i, 1)
        grid.setColumnStretch(1, 1)
        info_vbox.addLayout(grid)

        layout.addWidget(info_card)

        # ── 업데이트
        upd_card = Card()
        uv = QVBoxLayout(upd_card)
        uv.setContentsMargins(30, 22, 30, 22)
        uv.setSpacing(12)
        top = QHBoxLayout()
        top_text = QVBoxLayout()
        top_text.setSpacing(2)
        top_text.addWidget(label("업데이트", "CardTitle"))
        self.update_status = label(f"지금 버전: {APP_VERSION}", "Secondary")
        self.update_status.setTextFormat(Qt.PlainText)
        self.update_status.setWordWrap(True)
        top_text.addWidget(self.update_status)
        top.addLayout(top_text, 1)
        self.check_btn = QPushButton("지금 확인")
        self.check_btn.clicked.connect(self.check_update_requested.emit)
        top.addWidget(self.check_btn, 0, Qt.AlignVCenter)
        uv.addLayout(top)
        uv.addWidget(divider())
        row = QHBoxLayout()
        row_text = QVBoxLayout()
        row_text.setSpacing(2)
        row_text.addWidget(label("새 버전 자동 확인", "", "font-weight: 600;"))
        note = label(
            "켜 두면 실행 30초 뒤와 하루에 한 번 GitHub에 최신 버전을 물어봐요. "
            "이때 IP 주소가 GitHub에 전달되고, 그 밖의 개인 정보나 감상 기록은 보내지 않아요.",
            "Secondary", "font-size: 12px;",
        )
        note.setWordWrap(True)
        row_text.addWidget(note)
        row.addLayout(row_text, 1)
        self.auto_switch = ToggleSwitch()
        self.auto_switch.setAccessibleName("새 버전 자동 확인")
        self.auto_switch.setChecked(auto_check)
        self.auto_switch.toggled.connect(self.auto_check_toggled.emit)
        row.addWidget(self.auto_switch, 0, Qt.AlignVCenter)
        uv.addLayout(row)
        layout.addWidget(upd_card)
        layout.addStretch()

    def set_update_status(self, text: str, checking: bool = False) -> None:
        self.update_status.setText(text)
        self.check_btn.setEnabled(not checking)
        self.check_btn.setText("확인 중…" if checking else "지금 확인")
