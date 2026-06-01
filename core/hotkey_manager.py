import keyboard  # type: ignore


class HotkeyManager:
    """전역 단축키 등록 및 해제를 관리합니다."""

    def __init__(self, on_ghost_toggle, on_quit):
        """
        Parameters
        ----------
        on_ghost_toggle : callable
            고스트 모드 토글 콜백
        on_quit : callable
            프로그램 종료 콜백
        """
        self._on_ghost_toggle = on_ghost_toggle
        self._on_quit = on_quit

    def refresh(self, hotkey_ghost: str, hotkey_quit: str, log_fn=None) -> None:
        """기존 단축키를 모두 해제하고 새 단축키를 등록합니다."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass

        def _register(hotkey: str, callback, name: str):
            if not hotkey or not hotkey.strip():
                return
            try:
                keyboard.add_hotkey(hotkey.strip(), callback)
                print(f"[⌨️] {name} 단축키 등록: {hotkey}")
            except Exception as e:
                print(f"[⚠️] {name} 단축키 등록 실패 ({hotkey}): {e}")
                if log_fn:
                    log_fn(f"{name} 단축키 등록 실패: {hotkey}")

        _register(hotkey_ghost, self._on_ghost_toggle, "고스트 모드")
        _register(hotkey_quit, self._on_quit, "프로그램 종료")

        if log_fn:
            log_fn(f"단축키 갱신 완료: {hotkey_ghost} / {hotkey_quit}")

    def unhook_all(self) -> None:
        """모든 단축키를 해제합니다."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass
