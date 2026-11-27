"""Windows를 켤 때 자동 실행 (현재 사용자의 시작 프로그램, HKCU\\...\\Run).

- 관리자 권한이 필요 없는 사용자 단위 등록만 씁니다.
- 자동 실행일 때는 '--autostart'를 붙여, 창을 띄우지 않고 트레이로 조용히 시작합니다.
- exe로 실행할 때만 지원합니다 (소스 실행은 python.exe 경로가 등록되므로 막음).
"""

import sys

try:
    import winreg  # type: ignore
except ImportError:  # Windows가 아닌 환경(테스트 등)
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LyricsOverlay"
FLAG = "--autostart"


def supported() -> bool:
    return winreg is not None and bool(getattr(sys, "frozen", False))


def command(exe: str | None = None) -> str:
    return f'"{exe or sys.executable}" {FLAG}'


def _read() -> str | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return str(value)
    except OSError:
        return None


def is_enabled() -> bool:
    return _read() is not None


def set_enabled(on: bool) -> bool:
    """켜거나 끕니다. 성공하면 True."""
    if winreg is None or (on and not supported()):
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        print(f"[⚠️] 시작 프로그램 등록 변경 실패: {e}")
        return False


def sync_path() -> None:
    """켜져 있는데 exe 위치가 바뀌었으면(파일을 옮긴 경우) 지금 위치로 고칩니다."""
    if supported() and is_enabled() and _read() != command():
        set_enabled(True)


def launched_by_autostart(argv: list[str]) -> bool:
    return FLAG in argv
