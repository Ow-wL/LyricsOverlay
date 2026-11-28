"""멜론(웹 페이지·이미지 서버)에 보내는 요청을 한곳에서 다룹니다.

- 브라우저인 척하지 않고 앱 이름과 프로젝트 주소를 밝힙니다(User-Agent). 멜론에서 온 것처럼 보이는 Referer도 보내지 않습니다.
- 가사 검색·커버 받기를 합쳐 요청 사이에 최소 간격을 둡니다(여러 작업 스레드가 함께 씀).
- 멜론이 거절(403·429·503)하면 일정 시간 동안 모든 요청을 멈춥니다. 차단을 피해 가려고 하지 않습니다.
- 거절이 아니어도 짧은 시간에 요청이 여러 번 실패하면(다른 오류 응답, 연결 실패) 잠시 멈춥니다.
  중간에 성공한 요청이 있어도 셉니다 (검색은 되는데 곡 페이지만 계속 실패하는 경우를 놓치지 않도록).
- 멈춘 시각은 앱을 다시 켜도 이어지도록 밖에서 저장·복원할 수 있습니다 (`paused_until_epoch`, `restore_pause`).
"""

import threading
import time

from core.version import APP_VERSION

USER_AGENT = f"LyricsOverlay/{APP_VERSION} (+https://github.com/Ow-wL/LyricsOverlay)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"}

MIN_GAP_SEC = 1.0             # 멜론으로 가는 모든 요청 사이 최소 간격
BLOCK_PAUSE_SEC = 30 * 60     # 거절 응답을 받으면 이만큼 쉼
FAIL_LIMIT = 3                # 이 시간 안에 이만큼 실패하면
FAIL_WINDOW_SEC = 10 * 60
FAIL_PAUSE_SEC = 10 * 60      # 이만큼 쉼
_REFUSED = {403, 429, 503}

REFUSED = "refused"           # 쉬는 이유: 멜론이 거절함
ERRORS = "errors"             # 쉬는 이유: 요청이 여러 번 실패함

_lock = threading.Lock()
_last = 0.0
_blocked_until = 0.0          # time.monotonic 기준
_blocked_until_epoch = 0.0    # 같은 시각의 time.time 기준 (저장용)
_reason = ""
_fail_times: list[float] = []  # 최근 실패 시각 (time.monotonic)


class MelonPaused(Exception):
    """멜론 요청을 잠시 쉬는 중."""


def paused_for() -> float:
    """쉬는 중이면 남은 초, 아니면 0."""
    return max(0.0, _blocked_until - time.monotonic())


def pause_reason() -> str:
    """쉬는 중이면 그 이유(REFUSED 또는 ERRORS), 아니면 빈 문자열."""
    return _reason if paused_for() > 0 else ""


def pause_text() -> str:
    """쉬는 중일 때 화면·로그에 쓰는 설명. 쉬는 중이 아니면 빈 문자열."""
    left = paused_for()
    if left <= 0:
        return ""
    why = "멜론이 요청을 거절해" if _reason == REFUSED else "멜론 요청이 여러 번 실패해"
    return f"{why} {int(left) // 60 + 1}분 동안 쉬는 중"


def paused_until_epoch() -> float:
    """쉬는 중이면 끝나는 시각(time.time 기준), 아니면 0. 앱을 다시 켜도 이어지도록 저장할 때 씁니다."""
    return _blocked_until_epoch if paused_for() > 0 else 0.0


def restore_pause(until_epoch: float, reason: str = REFUSED) -> None:
    """지난 실행에서 저장한 '쉬는 중' 상태를 이어받습니다. 이미 지난 시각이면 아무 일도 하지 않습니다."""
    try:
        left = float(until_epoch) - time.time()
    except (TypeError, ValueError):
        return
    if left <= 0:
        return
    _pause(min(left, BLOCK_PAUSE_SEC), reason if reason in (REFUSED, ERRORS) else REFUSED)  # 시계가 틀려도 상한까지만


def wait_turn() -> None:
    """요청 직전에 부릅니다. 쉬는 중이면 MelonPaused, 아니면 최소 간격을 맞춰 기다립니다."""
    global _last
    with _lock:
        now = time.monotonic()
        if now < _blocked_until:
            raise MelonPaused(pause_text())
        wait = _last + MIN_GAP_SEC - now
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()


def report_status(status_code: int) -> None:
    """응답 코드를 알려 줍니다. 거절이면 한동안 모든 요청을 멈추고, 다른 오류 응답은 실패로 셉니다.

    404는 세지 않습니다: 곡이 내려갔거나 곡 ID가 바뀐 것이지, 요청이 막힌 신호가 아닙니다.
    """
    if status_code in _REFUSED:
        _pause(BLOCK_PAUSE_SEC, REFUSED)
        print(f"[⚠️] 멜론이 요청을 거절했습니다 (HTTP {status_code}). {BLOCK_PAUSE_SEC // 60}분 동안 요청하지 않습니다.")
    elif status_code >= 400 and status_code != 404:
        _note_failure(f"HTTP {status_code}")


def report_error() -> None:
    """응답을 받지 못한 실패(연결 실패, 시간 초과)를 알려 줍니다."""
    _note_failure("응답 없음")


def _note_failure(what: str) -> None:
    now = time.monotonic()
    with _lock:
        _fail_times[:] = [t for t in _fail_times if now - t < FAIL_WINDOW_SEC] + [now]
        tripped = len(_fail_times) >= FAIL_LIMIT
    if tripped:
        _pause(FAIL_PAUSE_SEC, ERRORS)
        print(f"[⚠️] 멜론 요청이 {FAIL_WINDOW_SEC // 60}분 안에 {FAIL_LIMIT}번 실패했습니다 ({what}). "
              f"{FAIL_PAUSE_SEC // 60}분 동안 요청하지 않습니다.")


def _pause(seconds: float, reason: str) -> None:
    global _blocked_until, _blocked_until_epoch, _reason
    with _lock:
        _fail_times.clear()
        until = time.monotonic() + seconds
        if until <= _blocked_until:
            return  # 이미 더 오래 쉬는 중입니다 (짧은 멈춤이 긴 멈춤을 줄이지 않게)
        _blocked_until = until
        _blocked_until_epoch = time.time() + seconds
        _reason = reason


def _reset_for_tests() -> None:
    global _last, _blocked_until, _blocked_until_epoch, _reason
    with _lock:
        _last = 0.0
        _blocked_until = 0.0
        _blocked_until_epoch = 0.0
        _reason = ""
        _fail_times.clear()
