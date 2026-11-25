import ctypes
import json
import os
from ctypes import wintypes
from dataclasses import dataclass

import cv2
import numpy as np
import win32con
import win32gui
import win32process
import win32ui

from core.utils import atomic_write_json

# ------------------------------------------------------------------ #
# 프로세스 확인
# ------------------------------------------------------------------ #

# 멜론 PC 플레이어 실행 파일 이름 (소문자). 제목만으로 찾으면 브라우저 등
# 엉뚱한 창을 잡아 투명하게 만들 수 있어서, 프로세스로 한 번 더 거릅니다.
MELON_EXE_NAMES = {"melon player.exe", "melon.exe"}

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
_kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


@dataclass(frozen=True)
class ProcessIdentity:
    """PID는 재사용되므로 실행 파일 이름과 생성 시각을 함께 봅니다."""
    pid: int
    exe: str
    created: int

    @property
    def is_melon(self) -> bool:
        return self.exe in MELON_EXE_NAMES


def get_process_identity(pid: int) -> ProcessIdentity | None:
    if not pid:
        return None
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not _kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return ProcessIdentity(pid, os.path.basename(buf.value).lower(), created)
    finally:
        _kernel32.CloseHandle(handle)


def get_window_pid(hwnd) -> int:
    try:
        return win32process.GetWindowThreadProcessId(hwnd)[1]
    except Exception:
        return 0


def get_window_identity(hwnd) -> ProcessIdentity | None:
    try:
        if not win32gui.IsWindow(hwnd):
            return None
    except Exception:
        return None
    return get_process_identity(get_window_pid(hwnd))


# ------------------------------------------------------------------ #
# 멜론 창 찾기
# ------------------------------------------------------------------ #

@dataclass
class TargetWindow:
    hwnd: int
    title: str
    process: ProcessIdentity


def find_melon_window(min_width: int = 200) -> TargetWindow | None:
    """멜론 프로세스의 보이는 창 중 가사를 읽을 창을 찾습니다.

    우선순위는 예전과 같습니다: 제목에 'Melon'이 있는 창 → 제목에 ' - '가 있는 창.
    """
    candidates: list[TargetWindow] = []

    def _collect(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            left, _top, right, _bottom = win32gui.GetWindowRect(hwnd)
            if right - left <= min_width:
                return True
            ident = get_window_identity(hwnd)
            if ident is not None and ident.is_melon:
                candidates.append(TargetWindow(hwnd, title, ident))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception:
        return None

    for cand in candidates:
        if "Melon" in cand.title:
            return cand
    for cand in candidates:
        if " - " in cand.title:
            return cand
    return None


# ------------------------------------------------------------------ #
# 캡처
# ------------------------------------------------------------------ #

def capture_covered_window(hwnd) -> np.ndarray | None:
    """Win32 PrintWindow를 이용해 가려진 창도 캡처합니다."""
    hwnd_dc = mfc_dc = save_dc = bitmap = old_obj = None
    try:
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
        w, h = max(right - left, 1), max(bot - top, 1)
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        old_obj = save_dc.SelectObject(bitmap)

        # 3 = PW_CLIENTONLY | PW_RENDERFULLCONTENT
        if not ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3):
            return None

        info = bitmap.GetInfo()
        img = np.frombuffer(bitmap.GetBitmapBits(True), dtype="uint8")
        img = img.reshape((info["bmHeight"], info["bmWidth"], 4))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception:
        return None
    finally:
        # 비트맵을 DC에서 빼낸 뒤 지우고, 중간에 실패해도 만든 것은 모두 정리합니다.
        for cleanup in (
            lambda: save_dc.SelectObject(old_obj) if save_dc and old_obj else None,
            lambda: win32gui.DeleteObject(bitmap.GetHandle()) if bitmap else None,
            lambda: save_dc.DeleteDC() if save_dc else None,
            lambda: mfc_dc.DeleteDC() if mfc_dc else None,
            lambda: win32gui.ReleaseDC(hwnd, hwnd_dc) if hwnd_dc else None,
        ):
            try:
                cleanup()
            except Exception:
                pass


# ------------------------------------------------------------------ #
# 외부 창 스타일 변경/복구
# ------------------------------------------------------------------ #

_GHOST_BITS = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT


class WindowStyleGuard:
    """멜론 창에 고스트 모드(투명 + 클릭통과 + 항상 위)를 적용하고 원래대로 되돌립니다.

    창마다 처음 건드리기 전의 상태를 기억했다가 그대로 복구합니다.
    원래 상태는 창을 바꾸기 *전에* 파일에 적어 두므로, 프로그램이 강제 종료돼도
    다음 실행 때 `recover_from_file()`로 되돌릴 수 있습니다.
    복구에 실패한 창은 기록에서 지우지 않습니다.
    """

    def __init__(self, data_dir: str):
        self._state_path = os.path.join(data_dir, "window_restore.json")
        # hwnd -> {"pid", "exe", "created", "exstyle", "layered": [key, alpha, flags] | None, "topmost"}
        self._originals: dict[int, dict] = {}

    # -- 공개 API ------------------------------------------------------ #

    def set_ghost(self, hwnd: int, ghost: bool) -> bool:
        """성공하면 True. 실패하면 다음 루프에서 다시 시도하도록 False."""
        return self._apply_ghost(hwnd) if ghost else self.restore(hwnd)

    def restore(self, hwnd: int) -> bool:
        original = self._originals.get(hwnd)
        if original is None:
            return True
        ok = self._restore_one(hwnd, original)
        if ok:
            del self._originals[hwnd]
            self._persist()
        return ok

    def restore_all(self) -> None:
        for hwnd in list(self._originals):
            self.restore(hwnd)

    def recover_from_file(self) -> int:
        """지난 실행이 비정상 종료돼 남은 창 상태를 복구합니다. 복구한 창 수를 반환."""
        if not os.path.exists(self._state_path):
            return 0
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                saved = {int(k): v for k, v in json.load(f).items()}
        except Exception as e:
            print(f"[⚠️] 창 상태 기록을 읽지 못했습니다: {e}")
            return 0

        recovered = 0
        for hwnd, original in saved.items():
            if not self._is_same_window(hwnd, original):
                continue  # 창이 이미 닫혔거나 다른 프로세스의 창 (복구 불필요)
            if self._restore_one(hwnd, original):
                recovered += 1
            else:
                self._originals[hwnd] = original  # 다음 기회에 다시 시도
        self._persist()
        return recovered

    # -- 내부 ---------------------------------------------------------- #

    @staticmethod
    def _is_same_window(hwnd: int, original: dict) -> bool:
        ident = get_window_identity(hwnd)
        return (
            ident is not None
            and ident.pid == original.get("pid")
            and ident.created == original.get("created")
            and ident.exe == original.get("exe")
        )

    def _apply_ghost(self, hwnd: int) -> bool:
        try:
            ident = get_window_identity(hwnd)
            if ident is None or not ident.is_melon:
                return False  # 창 핸들이 그사이 다른 프로세스 것이 됐을 수 있음

            if hwnd not in self._originals:
                exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                layered = None
                if exstyle & win32con.WS_EX_LAYERED:
                    try:
                        key, alpha, flags = win32gui.GetLayeredWindowAttributes(hwnd)
                        layered = [int(key), int(alpha), int(flags)]
                    except Exception:
                        layered = None  # UpdateLayeredWindow 방식의 창
                self._originals[hwnd] = {
                    "pid": ident.pid,
                    "exe": ident.exe,
                    "created": ident.created,
                    "exstyle": exstyle,
                    "layered": layered,
                    "topmost": bool(exstyle & win32con.WS_EX_TOPMOST),
                }
                if not self._persist():
                    # 기록이 없으면 강제 종료 시 되돌릴 수 없으니 적용하지 않습니다.
                    del self._originals[hwnd]
                    return False

            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | _GHOST_BITS)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 1, win32con.LWA_ALPHA)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
            return True
        except Exception as e:
            print(f"[⚠️] 고스트 모드 적용 실패: {e}")
            return False

    def _restore_one(self, hwnd: int, original: dict) -> bool:
        """원래 상태로 되돌립니다. 창이 이미 사라졌으면 복구할 것이 없으므로 True."""
        if not self._is_same_window(hwnd, original):
            return True
        target = original["exstyle"]
        layered = original.get("layered")
        try:
            current = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            topmost_bit = current & win32con.WS_EX_TOPMOST  # topmost는 SetWindowPos로만 바꿉니다

            if target & win32con.WS_EX_LAYERED and layered is not None:
                # SetLayeredWindowAttributes 방식이던 창: 속성을 원래 값으로
                win32gui.SetLayeredWindowAttributes(hwnd, layered[0], layered[1], layered[2])
                win32gui.SetWindowLong(
                    hwnd, win32con.GWL_EXSTYLE, (target & ~win32con.WS_EX_TOPMOST) | topmost_bit
                )
            else:
                # 레이어드가 아니었거나 UpdateLayeredWindow 방식이던 창:
                # 레이어드를 한 번 껐다가 원래 스타일로 되돌려야 우리가 건 속성이 사라집니다.
                win32gui.SetWindowLong(
                    hwnd, win32con.GWL_EXSTYLE,
                    (current & ~_GHOST_BITS & ~win32con.WS_EX_TOPMOST) | topmost_bit,
                )
                win32gui.SetWindowLong(
                    hwnd, win32con.GWL_EXSTYLE, (target & ~win32con.WS_EX_TOPMOST) | topmost_bit
                )

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST if original.get("topmost") else win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                | win32con.SWP_FRAMECHANGED,
            )
            return win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) == target
        except Exception as e:
            print(f"[⚠️] 창 상태 복구 실패 (hwnd={hwnd}): {e}")
            return False

    def _persist(self) -> bool:
        try:
            if self._originals:
                atomic_write_json(
                    self._state_path, {str(k): v for k, v in self._originals.items()}
                )
            elif os.path.exists(self._state_path):
                os.remove(self._state_path)
            return True
        except Exception as e:
            print(f"[⚠️] 창 상태 기록 실패: {e}")
            return False
