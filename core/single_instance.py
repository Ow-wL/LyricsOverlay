"""중복 실행 방지.

두 개가 동시에 돌면 같은 설정·통계 파일과 멜론 창 상태를 서로 덮어쓰므로 하나만 실행합니다.
- 잠금: Windows 이름 있는 뮤텍스 (현재 로그인 세션 범위)
- 두 번째 실행은 이미 떠 있는 프로그램에 "창 보여 줘" 신호만 보내고 끝납니다.
"""

import getpass
import re

import win32api
import win32event
import winerror
from PySide6.QtCore import QObject, Signal  # type: ignore
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # type: ignore


def _safe_user() -> str:
    try:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", getpass.getuser())[:40] or "user"
    except Exception:
        return "user"


_MUTEX_NAME = "Local\\Ow-wL.LyricsOverlay.SingleInstance"
_SERVER_NAME = f"Ow-wL.LyricsOverlay.{_safe_user()}"


class SingleInstance(QObject):
    """acquire()가 False면 이미 실행 중입니다 (이때 기존 창을 앞으로 불러 옵니다)."""

    activate_requested = Signal()

    def __init__(self):
        super().__init__()
        self._mutex = None
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        self._mutex = win32event.CreateMutex(None, False, _MUTEX_NAME)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            self._notify_running_instance()
            return False
        self._start_server()
        return True

    def _notify_running_instance(self) -> None:
        sock = QLocalSocket()
        sock.connectToServer(_SERVER_NAME)
        if sock.waitForConnected(1000):
            sock.write(b"show")
            sock.waitForBytesWritten(1000)
            sock.disconnectFromServer()

    def _start_server(self) -> None:
        QLocalServer.removeServer(_SERVER_NAME)
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.UserAccessOption)  # 같은 사용자만 접속
        if not server.listen(_SERVER_NAME):
            print(f"[⚠️] 실행 알림 서버를 열지 못했습니다: {server.errorString()}")
            return
        server.newConnection.connect(self._on_connection)
        self._server = server

    def _on_connection(self) -> None:
        while self._server and self._server.hasPendingConnections():
            conn = self._server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._on_ready(c))

    def _on_ready(self, conn: QLocalSocket) -> None:
        if bytes(conn.readAll()).startswith(b"show"):
            self.activate_requested.emit()
        conn.disconnectFromServer()
