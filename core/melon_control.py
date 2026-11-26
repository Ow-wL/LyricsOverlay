"""멜론에 재생 명령 보내기 (이전 곡 / 재생·일시정지 / 다음 곡).

멜론 PC 플레이어는 Windows 미디어 제어(SMTC)에 세션을 등록하지 않아서, 그 경로로는 명령을 보낼 수 없습니다.
Windows 미디어 키는 시스템 전체에 전달돼 앞에 떠 있는 다른 앱(브라우저·메신저 등 Chromium 계열)이
가로채거나 다른 플레이어가 함께 반응할 수 있습니다.
그래서 멜론 창에 WM_APPCOMMAND를 직접 보냅니다. 실제 멜론에서 이전·다음·재생/일시정지가
한 번씩 정확히 동작하는 것을 확인했습니다. (이전 곡은 3초 이상 들은 뒤에는 곡을 처음으로 되감는 것이 멜론의 동작입니다.)
"""

import ctypes
from ctypes import wintypes

import win32gui

from core.window_capture import get_window_identity

WM_APPCOMMAND = 0x0319
SMTO_ABORTIFHUNG = 0x0002
APPCOMMANDS = {"next": 11, "prev": 12, "play_pause": 14}  # APPCOMMAND_MEDIA_*


def find_control_window() -> int | None:
    """명령을 받을 멜론 최상위 창. 최소화·트레이로 숨긴 상태도 포함하되, 보이는 창을 먼저 고릅니다."""
    visible, hidden = [], []

    def _collect(hwnd, _):
        try:
            if not win32gui.GetWindowText(hwnd):
                return True
            ident = get_window_identity(hwnd)
            if ident is None or not ident.is_melon:
                return True
            (visible if win32gui.IsWindowVisible(hwnd) else hidden).append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception:
        return None
    for group in (visible, hidden):
        if group:
            return group[0]
    return None


def send_app_command(action: str) -> bool:
    """멜론 창에 명령을 보냅니다. 멜론 창이 없거나 응답하지 않으면 False."""
    cmd = APPCOMMANDS.get(action)
    if cmd is None:
        return False
    hwnd = find_control_window()
    if hwnd is None:
        return False
    result = ctypes.c_size_t(0)
    ok = ctypes.windll.user32.SendMessageTimeoutW(
        wintypes.HWND(hwnd), WM_APPCOMMAND, wintypes.WPARAM(hwnd), wintypes.LPARAM(cmd << 16),
        SMTO_ABORTIFHUNG, 500, ctypes.byref(result),
    )
    return bool(ok)
