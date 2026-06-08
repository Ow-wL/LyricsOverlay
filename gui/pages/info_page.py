"""프로그램 및 개발자 정보 페이지."""

from PySide6.QtCore import Qt  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gui.theme import UIConfig
from gui.widgets.card import Card


class InfoPage(QWidget):
    """프로그램 정보 및 개발자 정보를 표시하는 페이지."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(32)

        # 헤더
        header = QLabel("정보")
        header.setObjectName("PageHeader")
        header.setStyleSheet(
            f"font-size: {UIConfig.FS_HEADER_MAIN}; font-weight: 900;"
        )
        layout.addWidget(header)

        # 정보 카드
        info_card = Card()
        info_vbox = QVBoxLayout(info_card)
        info_vbox.setContentsMargins(32, 32, 32, 32)
        info_vbox.setSpacing(24)

        # 앱 이름 및 버전
        title_label = QLabel("Lyrics Overlay")
        title_label.setStyleSheet(
            f"font-size: 28px; font-weight: 900;"
        )
        version_label = QLabel("Version 1.0.1")
        version_label.setStyleSheet(
            f"font-size: {UIConfig.FS_TITLE_S}; font-weight: 600; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        
        info_vbox.addWidget(title_label)
        info_vbox.addWidget(version_label)
        
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #333333;")
        info_vbox.addWidget(line)

        # 개발자 정보 (사용자가 기입할 곳)
        dev_title = QLabel("개발자 정보")
        dev_title.setStyleSheet(f"font-size: {UIConfig.FS_TITLE_M}; font-weight: 800;")
        info_vbox.addWidget(dev_title)

        dev_desc = QLabel(
            "개발자: 이주형(Ow-wL)\n"
            "이메일: ganno1208@naver.com\n"
            "GitHub: https://github.com/Ow-wL\n\n"
        )
        dev_desc.setStyleSheet(
            f"font-size: {UIConfig.FS_DESC}; font-weight: 500; line-height: 1.5; color: {UIConfig.COLOR_SECONDARY_TEXT};"
        )
        info_vbox.addWidget(dev_desc)

        layout.addWidget(info_card)
        layout.addStretch()
