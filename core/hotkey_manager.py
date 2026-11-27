"""전역 단축키(Windows RegisterHotKey)와 미디어 키 보내기."""

import ctypes
import threading
import time
from ctypes import wintypes

# ------------------------------------------------------------------ #
# Windows 미디어 VK 코드
# ------------------------------------------------------------------ #
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3


def _send_media_key(vk_code: int) -> None:
    """keybd_event를 이용해 미디어 VK 키를 전역으로 전송합니다."""
    try:
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(
            vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0
        )
    except Exception as e:
        print(f"[⚠️] 미디어 키 전송 실패 (vk={hex(vk_code)}): {e}")


def send_next_track() -> None:
    _send_media_key(VK_MEDIA_NEXT_TRACK)


def send_prev_track() -> None:
    _send_media_key(VK_MEDIA_PREV_TRACK)


def send_play_pause() -> None:
    _send_media_key(VK_MEDIA_PLAY_PAUSE)


def is_typing_hotkey(hotkey: str) -> bool:
    """글자 하나(+Shift)만으로 된 조합인지 확인합니다.

    전역 단축키는 다른 프로그램에서 타이핑할 때도 발동하므로,
    'q'나 'shift+q' 같은 조합은 평범한 입력만으로 기능이 실행됩니다.
    """
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return False
    keys = [p for p in parts if p not in ("shift", "left shift", "right shift")]
    return len(keys) == 1 and len(keys[0]) == 1


# ------------------------------------------------------------------ #
# 단축키 문자열 → Windows 등록 값
# ------------------------------------------------------------------ #

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT,
         "win": MOD_WIN, "windows": MOD_WIN, "meta": MOD_WIN}
_NAMED_VK = {
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "backspace": 0x08, "esc": 0x1B, "escape": 0x1B,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23, "page up": 0x21, "page down": 0x22,
    "pause": 0x13, "print screen": 0x2C, "caps lock": 0x14, "num lock": 0x90, "scroll lock": 0x91,
}


def parse_hotkey(hotkey: str) -> tuple[int, int] | None:
    """'ctrl+shift+left' → (수정키 비트, 가상 키 코드). 해석할 수 없으면 None."""
    parts = [p.strip().lower() for p in (hotkey or "").split("+") if p.strip()]
    if not parts:
        return None
    mods, key = 0, None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        elif key is None:
            key = p
        else:
            return None  # 일반 키가 둘 이상
    if key is None:
        return None
    if key in _NAMED_VK:
        vk = _NAMED_VK[key]
    elif len(key) >= 2 and key[0] == "f" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1 and ("a" <= key <= "z" or "0" <= key <= "9"):
        vk = ord(key.upper())
    elif len(key) == 1:
        res = ctypes.windll.user32.VkKeyScanW(ord(key)) if hasattr(ctypes, "windll") else -1
        if res == -1 or res & 0xFF == 0xFF:
            return None
        vk = res & 0xFF
    else:
        return None
    return mods, vk


# ------------------------------------------------------------------ #
# HotkeyManager — Windows RegisterHotKey
# ------------------------------------------------------------------ #

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_USER = 0x0400
REPEAT_GUARD_SEC = 0.3  # 같은 단축키가 이 시간 안에 다시 오면 무시


class _HotkeyThread(threading.Thread):
    """RegisterHotKey는 등록한 스레드의 메시지 큐로 WM_HOTKEY를 보내므로, 전용 스레드에서 등록·수신합니다."""

    def __init__(self, entries: list[tuple[str, str, int, int, object]]):
        super().__init__(name="hotkeys", daemon=True)
        self.entries = entries          # (이름, 원래 문자열, 수정키, 가상 키, 콜백)
        self.failed: list[tuple[str, str]] = []
        self.ready = threading.Event()
        self.thread_id = 0

    def run(self) -> None:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, 0)  # 메시지 큐 만들기
        callbacks = {}
        for i, (name, text, mods, vk, cb) in enumerate(self.entries, start=1):
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                callbacks[i] = cb
            else:
                self.failed.append((name, text))
        self.ready.set()
        last: dict[int, float] = {}
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam in callbacks:
                    # 키를 누르고 있을 때 반복이 새어 들어와도 한 번만 (MOD_NOREPEAT에 더한 안전장치)
                    now = time.monotonic()
                    if now - last.get(msg.wParam, -1.0) < REPEAT_GUARD_SEC:
                        continue
                    last[msg.wParam] = now
                    try:
                        callbacks[msg.wParam]()
                    except Exception as e:
                        print(f"[⚠️] 단축키 처리 중 오류: {e}")
        finally:
            for i in callbacks:
                user32.UnregisterHotKey(None, i)

    def stop(self) -> None:
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
        self.join(timeout=2)


class HotkeyManager:
    """전역 단축키를 Windows 표준 방식(RegisterHotKey)으로 등록·해제합니다.

    - 키보드 전체를 지켜보는 훅을 쓰지 않습니다 (게임 안티치트가 문제 삼을 여지를 줄임).
    - MOD_NOREPEAT: 키를 누르고 있어도 한 번만 실행됩니다.
    - 등록한 조합은 이 앱이 차지하므로 다른 프로그램에서는 그 키가 동작하지 않습니다.
      다른 프로그램이 먼저 쓰고 있는 조합이면 등록에 실패하고, 로그에 알립니다.
    """

    def __init__(self, on_ghost_toggle, on_quit, on_media=None):
        self._on_ghost_toggle = on_ghost_toggle
        self._on_quit = on_quit
        # on_media(action): "prev"/"play_pause"/"next". 없으면 미디어 키를 바로 보냅니다.
        self._on_media = on_media
        self._thread: _HotkeyThread | None = None

    def refresh(
        self,
        hotkey_ghost: str,
        hotkey_quit: str,
        hotkey_next: str = "",
        hotkey_prev: str = "",
        hotkey_pause: str = "",
        log_fn=None,
    ) -> list[tuple[str, str]]:
        """기존 단축키를 모두 해제하고 새 단축키를 등록합니다. 등록하지 못한 (이름, 조합) 목록을 돌려줍니다."""
        self.unhook_all()
        media = self._on_media
        wanted = [
            ("고스트 모드", hotkey_ghost, self._on_ghost_toggle),
            ("프로그램 종료", hotkey_quit, self._on_quit),
            ("다음 곡", hotkey_next, (lambda: media("next")) if media else send_next_track),
            ("이전 곡", hotkey_prev, (lambda: media("prev")) if media else send_prev_track),
            ("일시정지/재생", hotkey_pause, (lambda: media("play_pause")) if media else send_play_pause),
        ]
        entries, problems = [], []
        for name, text, cb in wanted:
            if not text or not text.strip():
                continue
            if is_typing_hotkey(text):
                problems.append((name, text))
                if log_fn:
                    log_fn(f"{name} 단축키 무시: {text} (Ctrl/Alt 조합을 쓰세요)")
                continue
            parsed = parse_hotkey(text)
            if parsed is None:
                problems.append((name, text))
                if log_fn:
                    log_fn(f"{name} 단축키를 해석하지 못했어요: {text}")
                continue
            entries.append((name, text, parsed[0], parsed[1], cb))

        if entries and hasattr(ctypes, "windll"):
            self._thread = _HotkeyThread(entries)
            self._thread.start()
            self._thread.ready.wait(timeout=2)
            for name, text in self._thread.failed:
                problems.append((name, text))
                print(f"[⚠️] {name} 단축키 등록 실패 ({text}): 다른 프로그램이 이미 쓰는 조합일 수 있어요")
                if log_fn:
                    log_fn(f"{name} 단축키 등록 실패: {text} (다른 프로그램이 쓰는 조합인지 확인하세요)")
        if log_fn:
            log_fn("단축키 갱신 완료")
        return problems

    def unhook_all(self) -> None:
        """모든 단축키를 해제합니다."""
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
