"""멜론(웹 페이지·이미지 서버)에 보내는 요청을 한곳에서 다룹니다.

- 브라우저인 척하지 않고 앱 이름과 프로젝트 주소를 밝힙니다(User-Agent). 멜론에서 온 것처럼 보이는 Referer도 보내지 않습니다.
- 가사 검색·커버 받기를 합쳐 요청 사이에 최소 간격을 둡니다(여러 작업 스레드가 함께 씀).
- 멜론이 거절(403·429·503)하면 일정 시간 동안 모든 요청을 멈춥니다. 차단을 피해 가려고 하지 않습니다.
"""

import threading
import time

from core.version import APP_VERSION

USER_AGENT = f"LyricsOverlay/{APP_VERSION} (+https://github.com/Ow-wL/LyricsOverlay)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"}

MIN_GAP_SEC = 1.0             # 멜론으로 가는 모든 요청 사이 최소 간격
BLOCK_PAUSE_SEC = 30 * 60     # 거절 응답을 받으면 이만큼 쉼
_REFUSED = {403, 429, 503}

_lock = threading.Lock()
_last = 0.0
_blocked_until = 0.0


class MelonPaused(Exception):
    """멜론이 요청을 거절해 잠시 쉬는 중."""


def paused_for() -> float:
    """쉬는 중이면 남은 초, 아니면 0."""
    return max(0.0, _blocked_until - time.monotonic())


def wait_turn() -> None:
    """요청 직전에 부릅니다. 쉬는 중이면 MelonPaused, 아니면 최소 간격을 맞춰 기다립니다."""
    global _last
    with _lock:
        now = time.monotonic()
        if now < _blocked_until:
            raise MelonPaused(f"멜론이 요청을 거절해 {int(_blocked_until - now) // 60 + 1}분 동안 쉬는 중")
        wait = _last + MIN_GAP_SEC - now
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()


def report_status(status_code: int) -> None:
    """응답 코드를 알려 줍니다. 거절이면 한동안 모든 요청을 멈춥니다."""
    global _blocked_until
    if status_code in _REFUSED:
        with _lock:
            _blocked_until = time.monotonic() + BLOCK_PAUSE_SEC
        print(f"[⚠️] 멜론이 요청을 거절했습니다 (HTTP {status_code}). {BLOCK_PAUSE_SEC // 60}분 동안 요청하지 않습니다.")


def _reset_for_tests() -> None:
    global _last, _blocked_until
    with _lock:
        _last = 0.0
        _blocked_until = 0.0
