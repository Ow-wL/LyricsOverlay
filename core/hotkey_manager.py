import ctypes

import keyboard  # type: ignore

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


class _OncePerPress:
    """단축키를 누르고 있는 동안의 자동 반복을 무시하고, 한 번 누름에 한 번만 실행합니다."""

    def __init__(self, callback):
        self._callback = callback
        self._armed = True

    def __call__(self) -> None:
        if not self._armed:
            return
        self._armed = False
        self._callback()

    def rearm(self, _event=None) -> None:
        self._armed = True


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
# HotkeyManager
# ------------------------------------------------------------------ #


class HotkeyManager:
    """전역 단축키 등록 및 해제를 관리합니다."""

    def __init__(self, on_ghost_toggle, on_quit, on_media=None):
        self._on_ghost_toggle = on_ghost_toggle
        self._on_quit = on_quit
        # on_media(action): "prev"/"play_pause"/"next". 없으면 예전처럼 미디어 키를 바로 보냅니다.
        self._on_media = on_media

    def refresh(
        self,
        hotkey_ghost: str,
        hotkey_quit: str,
        hotkey_next: str = "",
        hotkey_prev: str = "",
        hotkey_pause: str = "",
        log_fn=None,
    ) -> None:
        """기존 단축키를 모두 해제하고 새 단축키를 등록합니다."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass

        def _register(hotkey: str, callback, name: str) -> None:
            if not hotkey or not hotkey.strip():
                return
            if is_typing_hotkey(hotkey):
                print(f"[⚠️] {name} 단축키 무시 ({hotkey}): 타이핑과 겹치는 조합")
                if log_fn:
                    log_fn(f"{name} 단축키 무시: {hotkey} (Ctrl/Alt 조합을 쓰세요)")
                return
            try:
                # 키를 누르고 있으면 Windows가 키 입력을 자동 반복하는데, 그때마다 실행하면
                # 1초만 눌러도 '이전 곡'이 10번 넘게 실행됩니다. 처음 누를 때 한 번만 실행하고,
                # 마지막 키(예: Ctrl+Shift+← 의 ←)를 뗄 때까지 반복 입력은 무시합니다.
                once = _OncePerPress(callback)
                keyboard.add_hotkey(hotkey.strip(), once, suppress=False)
                keyboard.on_release_key(hotkey.strip().split("+")[-1].strip(), once.rearm)
                print(f"[⌨️] {name} 단축키 등록: {hotkey}")
            except Exception as e:
                print(f"[⚠️] {name} 단축키 등록 실패 ({hotkey}): {e}")
                if log_fn:
                    log_fn(f"{name} 단축키 등록 실패: {hotkey}")

        _register(hotkey_ghost, self._on_ghost_toggle, "고스트 모드")
        _register(hotkey_quit, self._on_quit, "프로그램 종료")
        media = self._on_media
        _register(hotkey_next, (lambda: media("next")) if media else send_next_track, "다음 곡")
        _register(hotkey_prev, (lambda: media("prev")) if media else send_prev_track, "이전 곡")
        _register(hotkey_pause, (lambda: media("play_pause")) if media else send_play_pause, "일시정지/재생")

        if log_fn:
            log_fn("단축키 갱신 완료")

    def unhook_all(self) -> None:
        """모든 단축키를 해제합니다."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass
