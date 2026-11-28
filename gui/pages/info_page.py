"""프로그램 및 개발자 정보 페이지."""

import os

from PySide6.QtCore import Qt, Signal  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QFrame, QGridLayout, QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.version import APP_VERSION
from gui import icons
from gui.widgets.card import Card
from gui.widgets.glass import ToggleSwitch, divider, icon_chip, label, page_header


class InfoPage(QWidget):
    """프로그램 정보 및 개발자 정보, 업데이트 확인을 표시하는 페이지."""

    check_update_requested = Signal()
    auto_check_toggled = Signal(bool)
    diagnostic_log_toggled = Signal(bool)
    install_requested = Signal()

    def __init__(self, auto_check: bool = True, diagnostic_log: bool = True):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 14, 12, 6)
        outer.setSpacing(22)
        outer.addWidget(page_header("정보", "프로그램과 개발자 정보"))

        # 카드가 창 높이보다 길어지면 눌려서 글자가 잘리므로, 카드 영역은 스크롤합니다.
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 16, 16)
        layout.setSpacing(22)
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

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
        info_vbox.addWidget(divider())
        legal = QHBoxLayout()
        legal_text = label(
            "Lyrics Overlay는 MIT 라이선스로 공개된 비공식 도구입니다. 멜론(Melon)은 카카오엔터테인먼트의 상표이며, "
            "이 프로그램은 멜론과 제휴하지 않았습니다.",
            "Secondary", "font-size: 12px;",
        )
        legal_text.setWordWrap(True)
        legal.addWidget(legal_text, 1)
        self.notices_btn = QPushButton("오픈소스 라이선스")
        self.notices_btn.setToolTip("앱에 포함된 오픈소스 소프트웨어와 글꼴의 라이선스 전문을 엽니다")
        self.notices_btn.clicked.connect(self._open_notices)
        legal.addWidget(self.notices_btn, 0, Qt.AlignVCenter)
        info_vbox.addLayout(legal)

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
        # 새 버전이 있을 때만 보이는 버튼 (대시보드 알림을 닫아도 여기서 업데이트 가능)
        self.install_btn = QPushButton("업데이트")
        self.install_btn.setObjectName("PrimaryButton")
        self.install_btn.clicked.connect(self.install_requested.emit)
        self.install_btn.hide()
        top.addWidget(self.install_btn, 0, Qt.AlignVCenter)
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

        # 진단 로그: 문제가 생겼을 때 원인을 찾기 위한 기록
        log_card = Card()
        lv = QHBoxLayout(log_card)
        lv.setContentsMargins(30, 22, 30, 22)
        lv.setSpacing(14)
        log_text = QVBoxLayout()
        log_text.setSpacing(2)
        log_text.addWidget(label("진단 로그 남기기", "", "font-weight: 600;"))
        log_note = label(
            "앱이 한 일과 오류를 이 PC의 파일에 남겨요 (최대 약 1.5MB, 오래된 것부터 지움). "
            "곡 제목과 가수는 들어가고 가사는 들어가지 않으며, 어디로도 보내지 않아요. "
            "끄면 남아 있던 로그도 지우고, '감상 기록 저장'을 끄면 로그도 남기지 않아요. 문제를 제보할 때 이 파일을 함께 보내면 원인을 찾기 쉬워요.",
            "Secondary", "font-size: 12px;",
        )
        log_note.setWordWrap(True)
        log_text.addWidget(log_note)
        lv.addLayout(log_text, 1)
        self.open_log_btn = QPushButton("로그 폴더 열기")
        self.open_log_btn.clicked.connect(self._open_log_folder)
        lv.addWidget(self.open_log_btn, 0, Qt.AlignVCenter)
        self.log_switch = ToggleSwitch()
        self.log_switch.setAccessibleName("진단 로그 남기기")
        self.log_switch.setChecked(diagnostic_log)
        self.log_switch.toggled.connect(self.diagnostic_log_toggled.emit)
        lv.addWidget(self.log_switch, 0, Qt.AlignVCenter)
        layout.addWidget(log_card)
        layout.addStretch()

    @staticmethod
    def _open_log_folder() -> None:
        from PySide6.QtCore import QUrl  # type: ignore
        from PySide6.QtGui import QDesktopServices  # type: ignore
        from core.utils import state_dir

        folder = state_dir()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    @staticmethod
    def _open_notices() -> None:
        from PySide6.QtCore import QUrl  # type: ignore
        from PySide6.QtGui import QDesktopServices  # type: ignore
        from core.utils import resource_path

        path = resource_path("THIRD_PARTY_NOTICES.txt")
        if os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:  # 소스 실행 등으로 파일이 없으면 저장소의 파일을 엽니다
            QDesktopServices.openUrl(QUrl("https://github.com/Ow-wL/LyricsOverlay/blob/main/THIRD_PARTY_NOTICES.txt"))

    def set_update_status(self, text: str, checking: bool = False) -> None:
        self.update_status.setText(text)
        self.check_btn.setEnabled(not checking)
        self.check_btn.setText("확인 중…" if checking else "지금 확인")

    def show_install(self, can_install: bool) -> None:
        self.install_btn.setText("업데이트" if can_install else "다운로드 페이지 열기")
        self.install_btn.show()

    def hide_install(self) -> None:
        self.install_btn.hide()
