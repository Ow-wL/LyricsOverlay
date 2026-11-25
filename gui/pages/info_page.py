"""프로그램 및 개발자 정보 페이지."""

from PySide6.QtCore import Qt  # type: ignore
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget  # type: ignore

from core.version import APP_VERSION
from gui import icons
from gui.widgets.card import Card
from gui.widgets.glass import divider, icon_chip, label, page_header


class InfoPage(QWidget):
    """프로그램 정보 및 개발자 정보를 표시하는 페이지."""

    def __init__(self):
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
        layout.addStretch()
