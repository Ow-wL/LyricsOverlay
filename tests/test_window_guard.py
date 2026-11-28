"""멜론 창 고스트 모드 적용·복구 (WindowStyleGuard).

실제 Win32 창(숨김)을 만들어 확인합니다. 이 테스트 프로세스를 멜론인 것처럼 취급하도록
실행 파일 이름만 바꿔치기하므로, 실제 멜론 창은 건드리지 않습니다.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import win32con
import win32gui

from core import window_capture
from core.window_capture import WindowStyleGuard

GHOST = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT


def exstyle(hwnd: int) -> int:
    return win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)


def is_ghosted(hwnd: int) -> bool:
    return window_capture._is_ghost_state(exstyle(hwnd), window_capture._read_layered(hwnd))


def leave_ghosted(hwnd: int) -> None:
    """기록 없이 고스트 상태만 남깁니다 (다른 실행이 강제 종료된 뒤의 모습)."""
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle(hwnd) | GHOST)
    win32gui.SetLayeredWindowAttributes(hwnd, 0, 1, win32con.LWA_ALPHA)
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
    )


class WindowStyleGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_dir = os.path.join(self._tmp.name, "state")
        self.data_dir = os.path.join(self._tmp.name, "data")
        os.makedirs(self.data_dir)
        self.record = os.path.join(self.state_dir, "window_restore.json")

        # 이 프로세스의 창만 '멜론 창'으로 취급합니다.
        patcher = mock.patch.object(
            window_capture, "MELON_EXE_NAMES", {os.path.basename(sys.executable).lower()}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.hwnd = win32gui.CreateWindowEx(
            0, "STATIC", "guard-test", win32con.WS_POPUP, 0, 0, 320, 200, 0, 0, 0, None
        )
        self.addCleanup(self._destroy)
        self.original = exstyle(self.hwnd)

    def _destroy(self):
        if win32gui.IsWindow(self.hwnd):
            win32gui.DestroyWindow(self.hwnd)

    def guard(self) -> WindowStyleGuard:
        return WindowStyleGuard(self.state_dir, legacy_dirs=(self.data_dir,))

    def test_apply_then_restore(self):
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        self.assertTrue(is_ghosted(self.hwnd))
        self.assertTrue(os.path.exists(self.record))  # 창을 바꾸기 전에 기록부터 남김

        self.assertTrue(g.set_ghost(self.hwnd, False))
        self.assertEqual(exstyle(self.hwnd), self.original)
        self.assertFalse(os.path.exists(self.record))

    def test_leftover_ghost_is_not_recorded_as_original(self):
        """다른 실행이 남긴 고스트 상태를 원래 상태로 기억하면 복구해도 투명한 채로 남습니다."""
        leave_ghosted(self.hwnd)
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        with open(self.record, encoding="utf-8") as f:
            saved = json.load(f)[str(self.hwnd)]
        self.assertEqual(saved["exstyle"] & GHOST, 0)
        self.assertIsNone(saved["layered"])

        g.restore_all()
        self.assertFalse(is_ghosted(self.hwnd))
        self.assertEqual(exstyle(self.hwnd) & (GHOST | win32con.WS_EX_TOPMOST), 0)
        self.assertFalse(os.path.exists(self.record))

    def test_startup_heals_ghost_left_without_record(self):
        leave_ghosted(self.hwnd)
        self.assertEqual(self.guard().recover_from_file(), 1)
        self.assertFalse(is_ghosted(self.hwnd))

    def test_restore_without_record_heals_leftover(self):
        """'멜론 창 숨기기'가 꺼진 채 실행돼도 남아 있던 고스트 상태는 걷어냅니다."""
        leave_ghosted(self.hwnd)
        self.assertTrue(self.guard().set_ghost(self.hwnd, False))
        self.assertFalse(is_ghosted(self.hwnd))

    def test_recovers_after_kill_from_fixed_folder(self):
        """강제 종료 뒤 새 실행은 데이터 폴더가 달라도 같은 기록을 찾아 복구합니다."""
        self.assertTrue(self.guard().set_ghost(self.hwnd, True))  # 복구 없이 버려진 실행

        other = WindowStyleGuard(self.state_dir, legacy_dirs=(os.path.join(self._tmp.name, "other"),))
        self.assertEqual(other.recover_from_file(), 1)
        self.assertEqual(exstyle(self.hwnd), self.original)
        self.assertFalse(os.path.exists(self.record))

    def test_legacy_record_in_data_dir(self):
        """예전 버전이 데이터 폴더에 남긴 기록(원래 상태가 고스트로 잘못 적힌 것 포함)도 복구합니다."""
        ident = window_capture.get_window_identity(self.hwnd)
        leave_ghosted(self.hwnd)
        legacy = os.path.join(self.data_dir, "window_restore.json")
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump({str(self.hwnd): {
                "pid": ident.pid, "exe": ident.exe, "created": ident.created,
                "exstyle": exstyle(self.hwnd), "layered": [0, 1, win32con.LWA_ALPHA], "topmost": True,
            }}, f)

        self.assertEqual(self.guard().recover_from_file(), 1)
        self.assertFalse(is_ghosted(self.hwnd))
        self.assertFalse(os.path.exists(legacy))

    def test_lookup_failure_keeps_record(self):
        """창은 있는데 프로세스 확인에 실패하면 '사라졌다'로 보지 않고 기록을 남깁니다."""
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        with mock.patch.object(window_capture, "get_window_identity", return_value=None):
            self.assertFalse(g.restore(self.hwnd))
        self.assertTrue(os.path.exists(self.record))

        self.assertTrue(g.restore(self.hwnd))  # 다음 시도에서 복구
        self.assertEqual(exstyle(self.hwnd), self.original)

    def test_closed_window_needs_no_restore(self):
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        win32gui.DestroyWindow(self.hwnd)
        self.assertTrue(g.restore(self.hwnd))
        self.assertFalse(os.path.exists(self.record))

    def test_other_process_window_is_never_touched(self):
        # 실제 멜론 이름을 쓰면 테스트가 진짜 멜론 창을 건드릴 수 있어서, 없는 이름을 씁니다.
        with mock.patch.object(window_capture, "MELON_EXE_NAMES", {"no-such-player.exe"}):
            leave_ghosted(self.hwnd)
            g = self.guard()
            self.assertEqual(g.recover_from_file(), 0)
            self.assertFalse(g.set_ghost(self.hwnd, True))
            self.assertTrue(is_ghosted(self.hwnd))  # 멜론 창이 아니므로 그대로


if __name__ == "__main__":
    unittest.main()
