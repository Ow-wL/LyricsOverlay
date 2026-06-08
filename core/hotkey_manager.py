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


# ------------------------------------------------------------------ #
# HotkeyManager
# ------------------------------------------------------------------ #


class HotkeyManager:
    """전역 단축키 등록 및 해제를 관리합니다."""

    def __init__(self, on_ghost_toggle, on_quit):
        self._on_ghost_toggle = on_ghost_toggle
        self._on_quit = on_quit

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
            try:
                keyboard.add_hotkey(hotkey.strip(), callback, suppress=False)
                print(f"[⌨️] {name} 단축키 등록: {hotkey}")
            except Exception as e:
                print(f"[⚠️] {name} 단축키 등록 실패 ({hotkey}): {e}")
                if log_fn:
                    log_fn(f"{name} 단축키 등록 실패: {hotkey}")

        _register(hotkey_ghost, self._on_ghost_toggle, "고스트 모드")
        _register(hotkey_quit, self._on_quit, "프로그램 종료")
        _register(hotkey_next, send_next_track, "다음 곡")
        _register(hotkey_prev, send_prev_track, "이전 곡")
        _register(hotkey_pause, send_play_pause, "일시정지/재생")

        if log_fn:
            log_fn("단축키 갱신 완료")

    def unhook_all(self) -> None:
        """모든 단축키를 해제합니다."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass
