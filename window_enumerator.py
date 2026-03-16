"""
window_enumerator.py
Utility for listing and managing Win32 windows.
"""

import win32gui
import win32con
import win32process
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int

    def __str__(self) -> str:
        return f"{self.title} (HWND: {self.hwnd})"


class WindowEnumerator:
    """
    Enumerates all visible, top-level windows.
    Designed to be stateless so results are always fresh.
    """

    @staticmethod
    def get_all_windows() -> list[WindowInfo]:
        """Return a list of all visible windows that have a title."""
        results: list[WindowInfo] = []

        def _enum_callback(hwnd: int, _lparam) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title.strip():
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                pid = -1
            results.append(WindowInfo(hwnd=hwnd, title=title, pid=pid))
            return True

        win32gui.EnumWindows(_enum_callback, None)
        results.sort(key=lambda w: w.title.lower())
        return results

    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[tuple[int, int, int, int]]:
        """Return (left, top, right, bottom) for the given window, or None."""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return rect  # (left, top, right, bottom)
        except Exception:
            return None

    @staticmethod
    def bring_to_foreground(hwnd: int) -> None:
        """Attempt to bring a window to the foreground."""
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
