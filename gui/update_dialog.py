"""업데이트 대화상자: 변경 내용 → 내려받기(진행률·취소) → 검증 → 교체."""

import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QTimer  # type: ignore
from PySide6.QtGui import QTextDocument  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QDialog,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from core import update_install, updater
from core.version import APP_VERSION
from gui import icons
from gui.widgets.glass import icon_chip, label


class _NotesView(QTextBrowser):
    """릴리스 설명(마크다운)을 읽기 좋게 보여 줍니다.

    HTML은 해석하지 않고(MarkdownNoHTML), 링크를 따라가거나 이미지·파일을 불러오지 않습니다.
    """

    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.document().setDocumentMargin(10)

    def set_notes(self, text: str) -> None:
        features = QTextDocument.MarkdownFeature(
            QTextDocument.MarkdownDialectGitHub.value | QTextDocument.MarkdownNoHTML.value
        )
        self.document().setMarkdown(text, features)
        self.verticalScrollBar().setValue(0)  # 처음부터 읽히도록
        self.moveCursor(self.textCursor().MoveOperation.Start)

    def loadResource(self, _type, _name):  # 이미지 등 외부·로컬 자원은 불러오지 않음
        return None


class UpdateDialog(QDialog):
    """open()으로 띄웁니다 (exec()의 중첩 루프는 앱 메인 루프를 멈추므로).

    검증까지 끝나면 staged_path에 새 exe 경로를 담고 accept()합니다.
    """

    def __init__(self, info: updater.ReleaseInfo, parent=None):
        super().__init__(parent)
        self.info = info
        self.staged_path: str | None = None
        self._cancel = threading.Event()
        self._progress = (0, info.exe_size)
        self._future = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="download")

        self.setWindowTitle("업데이트")
        # 앱 테마는 메인 창 중앙 위젯에만 걸려 있어 대화상자에도 같은 스타일을 입힙니다.
        if parent is not None and hasattr(parent, "centralWidget") and parent.centralWidget():
            self.setStyleSheet(parent.centralWidget().styleSheet())
            self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(14)

        # 머리: 아이콘 · 제목 · 버전 변화
        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(icon_chip(icons.DOWNLOAD, 44))
        head_text = QVBoxLayout()
        head_text.setSpacing(2)
        head_text.addWidget(label("새 버전이 나왔어요", "", "font-size: 18px; font-weight: 800; letter-spacing: -0.3px;"))
        head_text.addWidget(label(f"{APP_VERSION}  →  {info.version}", "AccentValue", "font-size: 13px;"))
        head.addLayout(head_text, 1)
        lay.addLayout(head)

        lay.addWidget(label("변경 내용", "SectionLabel"))
        notes = _NotesView()
        notes.setObjectName("ReleaseNotes")
        notes.set_notes(info.notes.strip() or "변경 내용이 적혀 있지 않아요.")
        notes.setMinimumHeight(200)
        lay.addWidget(notes, 1)

        size_mb = info.exe_size / 1024 / 1024
        self.message = label(
            f"{size_mb:.0f}MB를 받은 뒤 GitHub의 파일 검증값(SHA-256)과 비교하고, 프로그램을 닫았다가 "
            "새 버전으로 바꿔 다시 시작해요. 받는 동안에도 가사 오버레이는 계속 동작해요.",
            "Secondary", "font-size: 12px;",
        )
        self.message.setWordWrap(True)
        lay.addWidget(self.message)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.hide()
        lay.addWidget(self.bar)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_btn = QPushButton("나중에")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.install_btn = QPushButton("지금 업데이트")
        self.install_btn.setObjectName("PrimaryButton")
        self.install_btn.setDefault(True)
        self.install_btn.clicked.connect(self._start)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.install_btn)
        lay.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)

    # -- 진행 ---------------------------------------------------------- #

    def _start(self) -> None:
        self.install_btn.setEnabled(False)
        self.cancel_btn.setText("취소")
        self.bar.show()
        self.message.setText("내려받는 중…")
        self._cancel.clear()

        def progress(done, total):
            self._progress = (done, total)

        self._future = self._pool.submit(update_install.download, self.info, progress, self._cancel.is_set)
        self._timer.start()

    def _tick(self) -> None:
        done, total = self._progress
        if total:
            self.bar.setValue(int(done * 1000 / total))
            self.message.setText(f"내려받는 중… {done / 1024 / 1024:.0f} / {total / 1024 / 1024:.0f}MB")
        if self._future is None or not self._future.done():
            return
        self._timer.stop()
        future, self._future = self._future, None
        try:
            self.staged_path = future.result()
        except Exception as e:
            self._fail(str(e))
            return
        self.message.setText("검증을 마쳤어요. 프로그램을 닫고 새 버전으로 바꿉니다…")
        self.accept()

    def _fail(self, text: str) -> None:
        self.bar.hide()
        self.message.setText(f"업데이트하지 못했어요: {text}\n지금 버전은 그대로예요. 릴리스 페이지에서 직접 받을 수도 있어요.")
        self.install_btn.setText("다시 시도")
        self.install_btn.setEnabled(True)
        self.cancel_btn.setText("닫기")

    def _on_cancel(self) -> None:
        if self._future is not None and not self._future.done():
            self._cancel.set()  # 작업 스레드가 다음 조각에서 멈추고 받던 파일을 지웁니다
            self.message.setText("취소하는 중…")
            return
        self.reject()

    def reject(self) -> None:
        if self._future is not None and not self._future.done():
            self._on_cancel()
            return  # 다운로드가 끝난 뒤(취소 반영 뒤) 닫힘
        self._timer.stop()
        self._pool.shutdown(wait=False)
        super().reject()

    def done(self, result) -> None:
        self._timer.stop()
        self._pool.shutdown(wait=False)
        super().done(result)
