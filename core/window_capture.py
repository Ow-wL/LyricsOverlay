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

from core.utils import atomic_write_json, state_dir

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


def recheck_window(target: TargetWindow | None, min_width: int = 200) -> TargetWindow | None:
    """이미 찾은 멜론 창이 아직 쓸 수 있으면 제목만 새로 읽어 돌려줍니다 (전체 창 열거보다 훨씬 쌈).

    창이 닫혔거나 최소화·숨김 상태면 None을 돌려주므로, 그때 find_melon_window()로 다시 찾습니다.
    """
    if target is None:
        return None
    try:
        hwnd = target.hwnd
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return None
        title = win32gui.GetWindowText(hwnd)
        left, _top, right, _bottom = win32gui.GetWindowRect(hwnd)
        if not title or right - left <= min_width:
            return None
        return TargetWindow(hwnd, title, target.process)
    except Exception:
        return None


def is_melon_minimized() -> bool:
    """멜론 창이 최소화돼 있어 가사를 읽을 수 없는 상태인지 확인합니다."""
    found = False

    def _check(hwnd, _):
        nonlocal found
        try:
            if win32gui.IsIconic(hwnd) and win32gui.GetWindowText(hwnd):
                ident = get_window_identity(hwnd)
                if ident is not None and ident.is_melon:
                    found = True
                    return False
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_check, None)
    except Exception:
        pass  # 콜백이 False를 돌려 열거를 멈추면 pywin32가 예외를 냅니다
    return found


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
_GHOST_ALPHA = 1  # 고스트 모드에서 거는 불투명도
_STATE_FILE = "window_restore.json"


def default_state_dir() -> str:
    r"""복구 기록을 두는 사용자별 고정 폴더 (%LOCALAPPDATA%\LyricsOverlay).

    데이터 폴더는 설정이나 환경 변수로 바뀔 수 있습니다. 기록을 거기에 두면, 다른 데이터 폴더로
    띄운 실행이 강제 종료됐을 때 다음 실행이 기록을 찾지 못해 멜론 창이 투명한 채로 남습니다.
    """
    return state_dir()


def _read_layered(hwnd) -> list[int] | None:
    try:
        key, alpha, flags = win32gui.GetLayeredWindowAttributes(hwnd)
        return [int(key), int(alpha), int(flags)]
    except Exception:
        return None  # 레이어드가 아니거나 UpdateLayeredWindow 방식의 창


def _is_ghost_state(exstyle: int, layered) -> bool:
    """이 앱이 건 고스트 상태(레이어드 + 클릭통과 + 불투명도 1)로 보이는지."""
    return (
        exstyle & _GHOST_BITS == _GHOST_BITS
        and layered is not None
        and layered[1] == _GHOST_ALPHA
        and bool(layered[2] & win32con.LWA_ALPHA)
    )


def _sanitize_original(original: dict) -> dict:
    """기록하려는 "원래 상태"가 사실은 고스트 상태라면 고스트를 걷어낸 상태로 바꿉니다.

    다른 실행이 복구하지 못하고 남긴 고스트 상태를 원래 상태로 기억하면, 복구가
    투명한 상태로 되돌리고 성공으로 끝나 버립니다. 진짜 원래 값은 알 수 없으므로
    항상 위는 끕니다 (투명한 채로 남는 것보다 낫습니다).
    """
    if not _is_ghost_state(original["exstyle"], original.get("layered")):
        return original
    return {
        **original,
        "exstyle": original["exstyle"] & ~_GHOST_BITS & ~win32con.WS_EX_TOPMOST,
        "layered": None,
        "topmost": False,
    }


class WindowStyleGuard:
    """멜론 창에 고스트 모드(투명 + 클릭통과 + 항상 위)를 적용하고 원래대로 되돌립니다.

    창마다 처음 건드리기 전의 상태를 기억했다가 그대로 복구합니다.
    원래 상태는 창을 바꾸기 *전에* 파일에 적어 두므로, 프로그램이 강제 종료돼도
    다음 실행 때 `recover_from_file()`로 되돌릴 수 있습니다.
    복구에 실패한 창은 기록에서 지우지 않습니다.

    기록은 데이터 폴더가 아니라 사용자별 고정 폴더에 둡니다 (`default_state_dir()` 참고).
    `legacy_dirs`는 예전 버전이 기록을 남겼을 수 있는 폴더(데이터 폴더)입니다.
    """

    def __init__(self, state_dir: str | None = None, legacy_dirs: tuple[str, ...] = ()):
        self._state_dir = state_dir or default_state_dir()
        self._state_path = os.path.join(self._state_dir, _STATE_FILE)
        self._legacy_paths = [
            path for path in (os.path.join(d, _STATE_FILE) for d in legacy_dirs if d)
            if os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(self._state_path))
        ]
        # hwnd -> {"pid", "exe", "created", "exstyle", "layered": [key, alpha, flags] | None, "topmost"}
        self._originals: dict[int, dict] = {}
        # 고정 폴더의 기록을 읽지 못한 동안에는, 기록할 것이 없다는 이유로 그 파일을 지우지 않습니다.
        self._keep_state_file = False

    # -- 공개 API ------------------------------------------------------ #

    def set_ghost(self, hwnd: int, ghost: bool) -> bool:
        """성공하면 True. 실패하면 다음 루프에서 다시 시도하도록 False."""
        return self._apply_ghost(hwnd) if ghost else self.restore(hwnd)

    def restore(self, hwnd: int) -> bool:
        original = self._originals.get(hwnd)
        if original is None:
            # 기록은 없는데 고스트 상태로 남아 있는 멜론 창이면 걷어냅니다.
            return self._heal_orphan(hwnd)
        ok = self._restore_one(hwnd, original)
        if ok:
            del self._originals[hwnd]
            self._persist()
        return ok

    def restore_all(self) -> None:
        for hwnd in list(self._originals):
            try:
                self.restore(hwnd)
            except Exception as e:  # 한 창에서 실패해도 나머지 창은 복구합니다
                print(f"[⚠️] 창 상태 복구 실패 (hwnd={hwnd}): {e}")

    def recover_from_file(self) -> int:
        """지난 실행이 비정상 종료돼 남은 창 상태를 복구합니다. 복구한 창 수를 반환.

        기록이 없어도 고스트 상태로 남아 있는 멜론 창은 함께 되돌립니다 (`heal_orphans`).
        """
        saved: dict[int, dict] = {}
        unreadable: set[str] = set()  # 있는데 지금 읽지 못한 기록 (지우지 않고 다음 실행에서 다시 읽음)
        for path in [*self._legacy_paths, self._state_path]:  # 고정 폴더의 기록이 우선
            records = self._load(path)
            if records is None:
                unreadable.add(path)
            else:
                saved.update(records)
        self._keep_state_file = self._state_path in unreadable

        recovered = 0
        for hwnd, original in saved.items():
            try:
                original = _sanitize_original(original)
                status = self._window_status(hwnd, original)
                if status == "gone":
                    continue  # 창이 이미 닫혔거나 다른 프로세스의 창 (복구 불필요)
                if status == "same" and self._restore_one(hwnd, original):
                    recovered += 1
                    continue
            except Exception as e:  # 한 기록에서 실패해도 나머지 기록과 창은 계속 처리합니다
                print(f"[⚠️] 창 상태 복구 실패 (hwnd={hwnd}): {e}")
            self._originals[hwnd] = original  # 다음 기회에 다시 시도
        if self._persist():
            for path in self._legacy_paths:  # 남은 기록은 고정 폴더로 옮겨졌습니다
                try:
                    if path not in unreadable and os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
        return recovered + self.heal_orphans()

    def heal_orphans(self) -> int:
        """기록 없이 고스트 상태로 남은 멜론 창을 찾아 되돌립니다. 되돌린 창 수를 반환.

        기록이 다른 곳에 남았거나 지워진 채 투명한 창만 남은 경우를 위한 안전망입니다.
        이 앱이 고스트를 거는 창은 보이고 제목이 있는 창뿐이므로, 그런 창만 대상으로 삼습니다
        (멜론이 스스로 쓰는 숨은 보조 창은 건드리지 않습니다).
        """
        suspects: list[int] = []

        def _collect(hwnd, _):
            try:
                if (
                    hwnd not in self._originals
                    and win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & _GHOST_BITS == _GHOST_BITS
                    and win32gui.IsWindowVisible(hwnd)
                    and win32gui.GetWindowText(hwnd)
                ):
                    suspects.append(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(_collect, None)
        except Exception:
            pass

        healed = 0
        for hwnd in suspects:
            try:
                if not _is_ghost_state(
                    win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE), _read_layered(hwnd)
                ):
                    continue
                if self._heal_orphan(hwnd) and not _is_ghost_state(
                    win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE), _read_layered(hwnd)
                ):
                    healed += 1
            except Exception:
                pass
        return healed

    # -- 내부 ---------------------------------------------------------- #

    @staticmethod
    def _read_text(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def _load(cls, path: str) -> dict[int, dict] | None:
        """기록을 읽습니다. 파일은 있는데 지금 열 수 없으면(잠김 등) None.

        None이면 그 파일을 지우지 않습니다: 잠깐 못 읽은 것을 "기록 없음"으로 보면 멀쩡한 기록을 잃습니다.
        내용이 깨진 파일은 다시 읽어도 쓸 수 없으므로 빈 기록으로 봅니다.
        """
        if not os.path.exists(path):
            return {}
        try:
            text = cls._read_text(path)
        except OSError as e:
            print(f"[⚠️] 창 상태 기록을 지금 읽을 수 없습니다 (남겨 둠): {e}")
            return None
        except ValueError as e:  # UTF-8이 아닌 내용 (깨진 파일)
            print(f"[⚠️] 창 상태 기록이 깨져 있어 쓰지 않습니다: {e}")
            return {}
        try:
            return {
                int(k): v for k, v in json.loads(text).items()
                if isinstance(v, dict) and isinstance(v.get("exstyle"), int)
                and (v.get("layered") is None or (
                    isinstance(v.get("layered"), list) and len(v["layered"]) == 3
                    and all(isinstance(x, int) for x in v["layered"])
                ))
            }
        except Exception as e:
            print(f"[⚠️] 창 상태 기록이 깨져 있어 쓰지 않습니다: {e}")
            return {}

    @staticmethod
    def _window_status(hwnd: int, original: dict) -> str:
        """"same": 기록한 그 창 / "gone": 닫혔거나 다른 창 / "unknown": 창은 있는데 확인 실패.

        확인에 잠깐 실패한 것을 사라진 것으로 보면 복구도 안 하고 기록까지 지우게 됩니다.
        """
        try:
            if not win32gui.IsWindow(hwnd):
                return "gone"
        except Exception:
            return "gone"
        try:
            ident = get_window_identity(hwnd)
        except Exception:
            ident = None
        if ident is None:
            return "unknown"
        if (
            ident.is_melon  # 기록 파일이 바뀌어도 멜론이 아닌 창은 절대 건드리지 않습니다
            and ident.pid == original.get("pid")
            and ident.created == original.get("created")
            and ident.exe == original.get("exe")
        ):
            return "same"
        return "gone"

    def _apply_ghost(self, hwnd: int) -> bool:
        try:
            ident = get_window_identity(hwnd)
            if ident is None or not ident.is_melon:
                return False  # 창 핸들이 그사이 다른 프로세스 것이 됐을 수 있음

            if hwnd not in self._originals:
                exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                layered = _read_layered(hwnd) if exstyle & win32con.WS_EX_LAYERED else None
                # 이미 고스트 상태인 창(다른 실행이 남긴 것)은 그 상태를 원래 상태로 삼지 않습니다.
                self._originals[hwnd] = _sanitize_original({
                    "pid": ident.pid,
                    "exe": ident.exe,
                    "created": ident.created,
                    "exstyle": exstyle,
                    "layered": layered,
                    "topmost": bool(exstyle & win32con.WS_EX_TOPMOST),
                })
                if not self._persist():
                    # 기록이 없으면 강제 종료 시 되돌릴 수 없으니 적용하지 않습니다.
                    del self._originals[hwnd]
                    return False

            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | _GHOST_BITS)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, _GHOST_ALPHA, win32con.LWA_ALPHA)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
            return True
        except Exception as e:
            print(f"[⚠️] 고스트 모드 적용 실패: {e}")
            return False

    def _heal_orphan(self, hwnd: int) -> bool:
        """기록 없이 고스트 상태로 남은 멜론 창이면 고스트를 걷어냅니다. 할 일이 없으면 True."""
        try:
            exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            layered = _read_layered(hwnd) if exstyle & win32con.WS_EX_LAYERED else None
            if not _is_ghost_state(exstyle, layered):
                return True
            ident = get_window_identity(hwnd)
            if ident is None:
                return False  # 창은 있는데 프로세스 확인에 실패: 다음에 다시 시도
            if not ident.is_melon:
                return True  # 멜론이 아닌 창은 건드리지 않습니다
            return self._restore_one(hwnd, _sanitize_original({
                "pid": ident.pid,
                "exe": ident.exe,
                "created": ident.created,
                "exstyle": exstyle,
                "layered": layered,
                "topmost": True,
            }))
        except Exception:
            return True  # 창이 그사이 닫힘

    def _restore_one(self, hwnd: int, original: dict) -> bool:
        """원래 상태로 되돌립니다. 창이 이미 사라졌으면 복구할 것이 없으므로 True."""
        status = self._window_status(hwnd, original)
        if status == "gone":
            return True
        if status == "unknown":
            return False  # 기록을 남겨 두고 다음에 다시 시도
        target = original["exstyle"]
        layered = original.get("layered")
        try:
            current = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            topmost_bit = current & win32con.WS_EX_TOPMOST  # topmost는 SetWindowPos로만 바꿉니다

            if target & win32con.WS_EX_LAYERED and layered is not None:
                # SetLayeredWindowAttributes 방식이던 창: 스타일을 먼저 되돌리고 속성을 원래 값으로.
                # (지금 레이어드가 아닌 창에 속성부터 걸면 실패합니다.)
                win32gui.SetWindowLong(
                    hwnd, win32con.GWL_EXSTYLE, (target & ~win32con.WS_EX_TOPMOST) | topmost_bit
                )
                win32gui.SetLayeredWindowAttributes(hwnd, layered[0], layered[1], layered[2])
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
            # 스타일이 원래 값과 같고, 고스트 상태도 실제로 풀렸는지까지 확인합니다.
            after = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            return after == target and not _is_ghost_state(after, _read_layered(hwnd))
        except Exception as e:
            print(f"[⚠️] 창 상태 복구 실패 (hwnd={hwnd}): {e}")
            return False

    def _persist(self) -> bool:
        try:
            if self._originals and self._keep_state_file:
                # 아까 읽지 못한 기록 위에 덮어쓰기 전에 한 번 더 읽어, 거기 있던 창도 함께 기록합니다.
                # 여전히 읽을 수 없으면 쓰지 않습니다 (기록을 못 남기면 고스트도 적용하지 않습니다).
                pending = self._load(self._state_path)
                if pending is None:
                    return False
                for hwnd, original in pending.items():
                    mine = self._originals.get(hwnd)
                    same_window = mine is not None and all(
                        mine.get(k) == original.get(k) for k in ("pid", "exe", "created")
                    )
                    if mine is None or same_window:  # 같은 창이면 먼저 적힌 쪽이 진짜 원래 상태
                        self._originals[hwnd] = _sanitize_original(original)
            if self._originals:
                os.makedirs(self._state_dir, exist_ok=True)
                atomic_write_json(
                    self._state_path, {str(k): v for k, v in self._originals.items()}
                )
                self._keep_state_file = False  # 새 기록으로 바꿨으므로 보존할 옛 파일은 더 없습니다
            elif os.path.exists(self._state_path) and not self._keep_state_file:
                os.remove(self._state_path)
            return True
        except Exception as e:
            print(f"[⚠️] 창 상태 기록 실패: {e}")
            return False
