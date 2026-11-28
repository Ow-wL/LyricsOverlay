r"""진단 로그 파일.

문제가 생겼을 때 원인을 찾을 수 있도록, 앱이 한 일과 오류를 사용자별 고정 폴더
(%LOCALAPPDATA%\LyricsOverlay\LyricsOverlay.log)에 남깁니다. PC 밖으로 보내지 않습니다.

- 남기는 것: 대시보드 '최근 활동'과 같은 줄(곡 제목·가수 포함), 경고·오류 메시지, 예외 내용.
  잡히지 않은 예외는 Python이 stderr로 찍으므로 그대로 로그에 들어갑니다 (창 모드 exe에는 콘솔이 없어 여기에만 남습니다).
- 남기지 않는 것: 가사 문장. 콘솔에 가사를 찍는 곳은 `console()`을 써서 로그를 거치지 않습니다.
  (그 밖의 print는 모두 로그에 들어가므로, 가사를 print로 찍지 마세요.)
- 크기: 파일 하나 512KB, 예전 파일 2개까지 (넘으면 오래된 것부터 지움).
- 설정에서 끄거나 '감상 기록 저장'을 끄면 남기지 않습니다 (`start`의 should_log).
"""

import logging
import logging.handlers
import os
import platform
import sys
import threading
from typing import Callable

from core.utils import state_dir
from core.version import APP_VERSION

LOG_NAME = "LyricsOverlay.log"
MAX_BYTES = 512 * 1024
BACKUPS = 2

_logger: logging.Logger | None = None
_should_log: Callable[[], bool] = lambda: True
_real_stdout = None
_path: str | None = None
_busy = threading.local()


def log_path(directory: str | None = None) -> str:
    return os.path.join(directory or state_dir(), LOG_NAME)


def current_path() -> str | None:
    """로그를 쓰고 있는 파일 경로 (시작하지 않았으면 None)."""
    return _path


def start(should_log: Callable[[], bool] | None = None, directory: str | None = None) -> str | None:
    """로그 파일을 열고 print·예외를 함께 남기도록 연결합니다. 실패해도 앱은 계속 실행됩니다."""
    global _logger, _should_log, _real_stdout, _path
    if _logger is not None:
        return _path
    try:
        path = log_path(directory)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8", delay=True
        )
        # 파일에 쓰지 못할 때 logging이 stderr로 내는 안내는 다시 이 로그로 돌아오므로 끕니다.
        handler.handleError = lambda record: None
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger = logging.getLogger("lyricsoverlay.diagnostic")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.handlers[:] = [handler]
    except Exception as e:
        print(f"[⚠️] 진단 로그를 시작하지 못했습니다: {e}")
        return None

    _logger, _path = logger, path
    if should_log is not None:
        _should_log = should_log
    _real_stdout = sys.stdout
    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr, prefix="[stderr] ")
    write(f"=== 시작: Lyrics Overlay {APP_VERSION} ({'exe' if getattr(sys, 'frozen', False) else '소스'}), "
          f"{platform.platform()} ===")
    return path


def stop() -> None:
    """print 연결을 풀고 파일을 닫습니다 (테스트·종료용)."""
    global _logger, _should_log, _real_stdout, _path
    if _logger is None:
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if isinstance(stream, _Tee):
            setattr(sys, stream_name, stream.inner)
    for handler in list(_logger.handlers):
        handler.close()
        _logger.removeHandler(handler)
    _logger, _should_log, _real_stdout, _path = None, (lambda: True), None, None


def write(message: str) -> None:
    """한 줄을 남깁니다. 가사 문장은 넘기지 마세요."""
    logger = _logger
    if logger is None or getattr(_busy, "on", False):
        return
    _busy.on = True  # 로그를 쓰는 도중에 생긴 출력이 다시 로그로 들어오지 않게
    try:
        if not _should_log():
            return
        for line in str(message).splitlines():
            if line.strip():
                logger.info(line.rstrip())
    except Exception:
        pass  # 로그 때문에 앱이 멈추면 안 됩니다
    finally:
        _busy.on = False


def enabled() -> bool:
    """지금 로그를 남기는 상태인지."""
    try:
        return _logger is not None and bool(_should_log())
    except Exception:
        return False


def clear() -> int:
    """남아 있는 로그 파일을 지웁니다 (로그를 끌 때). 지운 파일 수."""
    if _logger is None or _path is None:
        return 0
    removed = 0
    for handler in _logger.handlers:
        try:
            handler.acquire()
            try:
                handler.close()  # delay=True라 다음에 쓸 때 다시 엽니다
            finally:
                handler.release()
        except Exception:
            pass
    for name in [_path] + [f"{_path}.{i}" for i in range(1, BACKUPS + 1)]:
        try:
            os.remove(name)
            removed += 1
        except OSError:
            pass
    return removed


def console(*args) -> None:
    """로그 파일을 거치지 않고 콘솔에만 찍습니다 (가사처럼 파일에 남기면 안 되는 내용)."""
    stream = _real_stdout if _logger is not None else sys.stdout
    if stream is None:
        return  # 창 모드 exe에는 콘솔이 없습니다
    try:
        print(*args, file=stream)
    except Exception:
        pass


class _Tee:
    """원래 출력으로 그대로 보내면서, 완성된 줄을 로그 파일에도 남깁니다."""

    def __init__(self, inner, prefix: str = ""):
        self.inner = inner
        self._prefix = prefix
        self._buf = ""
        self._lock = threading.Lock()

    def write(self, text) -> int:
        text = str(text)
        if self.inner is not None:
            try:
                self.inner.write(text)
            except Exception:
                pass
        if not enabled():
            self._buf = ""  # 꺼져 있는 동안 찍힌 내용이 나중에 켠 뒤 함께 남지 않게
            return len(text)
        with self._lock:
            self._buf += text
            *lines, self._buf = self._buf.split("\n")
            if len(self._buf) > 4000:  # 줄바꿈 없이 길게 이어지는 출력
                lines.append(self._buf)
                self._buf = ""
        for line in lines:
            if line.strip():
                write(self._prefix + line)
        return len(text)

    def flush(self) -> None:
        if self.inner is not None:
            try:
                self.inner.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        try:
            return bool(self.inner is not None and self.inner.isatty())
        except Exception:
            return False

    @property
    def encoding(self) -> str:
        return getattr(self.inner, "encoding", None) or "utf-8"

    def __getattr__(self, name):  # reconfigure, fileno 등은 원래 출력에 맡깁니다
        return getattr(self.inner, name)
