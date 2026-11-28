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


ORIGINAL_ALPHA = 200


def make_translucent(hwnd: int) -> None:
    """창이 원래부터 반투명(레이어드)이던 것처럼 만듭니다.

    '항상 위'는 다른 창들의 상태에 따라 Windows가 받아 주지 않을 때가 있어 테스트에 쓰지 않습니다.
    """
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle(hwnd) | win32con.WS_EX_LAYERED)
    win32gui.SetLayeredWindowAttributes(hwnd, 0, ORIGINAL_ALPHA, win32con.LWA_ALPHA)


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

        self.hwnd = self.make_window()
        self.original = exstyle(self.hwnd)

    def make_window(self) -> int:
        # 멜론 창처럼 '보이고 제목이 있는' 창. 화면 밖에 두고 활성화하지 않습니다.
        hwnd = win32gui.CreateWindowEx(
            0, "STATIC", "guard-test", win32con.WS_POPUP, -32000, -32000, 320, 200, 0, 0, 0, None
        )
        self.addCleanup(lambda: win32gui.IsWindow(hwnd) and win32gui.DestroyWindow(hwnd))
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        return hwnd

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

    def test_restores_originally_translucent_window(self):
        make_translucent(self.hwnd)
        original = exstyle(self.hwnd)
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        self.assertTrue(is_ghosted(self.hwnd))
        self.assertTrue(g.set_ghost(self.hwnd, False))
        self.assertEqual(exstyle(self.hwnd), original)
        self.assertEqual(window_capture._read_layered(self.hwnd), [0, ORIGINAL_ALPHA, win32con.LWA_ALPHA])

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

    def test_startup_heal_skips_hidden_window(self):
        """시작할 때의 자동 복구는 보이는 창만 대상으로 합니다 (멜론의 숨은 보조 창을 건드리지 않게)."""
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
        leave_ghosted(self.hwnd)
        g = self.guard()
        self.assertEqual(g.recover_from_file(), 0)
        self.assertTrue(is_ghosted(self.hwnd))

        self.assertTrue(g.set_ghost(self.hwnd, False))  # 앱이 직접 다루는 창이 되면 걷어냄
        self.assertFalse(is_ghosted(self.hwnd))

    def test_heal_retries_after_lookup_failure(self):
        leave_ghosted(self.hwnd)
        g = self.guard()
        with mock.patch.object(window_capture, "get_window_identity", return_value=None):
            self.assertFalse(g.set_ghost(self.hwnd, False))
        self.assertTrue(is_ghosted(self.hwnd))
        self.assertTrue(g.set_ghost(self.hwnd, False))
        self.assertFalse(is_ghosted(self.hwnd))

    def test_unreadable_record_is_kept(self):
        """기록 파일을 잠깐 읽지 못했다고 지우면 멀쩡한 기록을 잃습니다. 남겨 두고 다음 실행에서 씁니다."""
        make_translucent(self.hwnd)  # 기록이 있어야만 되살릴 수 있는 원래 상태
        original = exstyle(self.hwnd)
        self.assertTrue(original & win32con.WS_EX_LAYERED)
        self.assertTrue(self.guard().set_ghost(self.hwnd, True))  # 복구 없이 버려진 실행
        legacy = os.path.join(self.data_dir, "window_restore.json")
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("{}")

        with mock.patch.object(WindowStyleGuard, "_read_text", side_effect=PermissionError("locked")):
            self.guard().recover_from_file()
        self.assertTrue(os.path.exists(self.record))
        self.assertTrue(os.path.exists(legacy))
        # 기록 없이 걷어내기만 했으므로 원래의 반투명 설정은 사라져 있습니다.
        self.assertFalse(exstyle(self.hwnd) & win32con.WS_EX_LAYERED)

        self.guard().recover_from_file()  # 다음 실행: 이번에는 읽혀서 원래 상태(반투명 포함)로
        self.assertEqual(exstyle(self.hwnd), original)
        self.assertEqual(window_capture._read_layered(self.hwnd), [0, ORIGINAL_ALPHA, win32con.LWA_ALPHA])
        self.assertFalse(os.path.exists(self.record))
        self.assertFalse(os.path.exists(legacy))

    def test_unreadable_record_is_not_overwritten(self):
        """읽지 못한 기록이 있는 동안에는 새 기록으로 덮어쓰지 않고, 읽히면 합쳐서 씁니다."""
        other = self.make_window()
        self.assertTrue(self.guard().set_ghost(other, True))  # 버려진 실행이 남긴 기록
        with open(self.record, encoding="utf-8") as f:
            abandoned = json.load(f)

        g = self.guard()
        with mock.patch.object(WindowStyleGuard, "_read_text", side_effect=PermissionError("locked")):
            g.recover_from_file()
            self.assertFalse(g.set_ghost(self.hwnd, True))  # 기록을 못 남기므로 적용하지 않음
        self.assertFalse(is_ghosted(self.hwnd))
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(json.load(f), abandoned)

        self.assertTrue(g.set_ghost(self.hwnd, True))  # 읽히면 예전 기록과 합쳐서 기록
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)), {str(self.hwnd), str(other)})

    def test_bad_encoding_record_does_not_stop_recovery(self):
        os.makedirs(self.state_dir)
        with open(self.record, "wb") as f:
            f.write(b"\xff\xfe\x00broken")
        leave_ghosted(self.hwnd)
        self.assertEqual(self.guard().recover_from_file(), 1)  # 깨진 기록은 버리고 창은 되돌림
        self.assertFalse(is_ghosted(self.hwnd))
        self.assertFalse(os.path.exists(self.record))

    def test_recovery_continues_after_error_in_one_record(self):
        other = self.make_window()
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        self.assertTrue(g.set_ghost(other, True))  # 복구 없이 버려진 실행

        real, calls = WindowStyleGuard._window_status, []

        def flaky(hwnd, original):
            calls.append(hwnd)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return real(hwnd, original)

        fresh = self.guard()
        with mock.patch.object(WindowStyleGuard, "_window_status", side_effect=flaky):
            fresh.recover_from_file()
        failed = calls[0]
        self.assertEqual(sum(is_ghosted(h) for h in (self.hwnd, other)), 1)
        self.assertTrue(is_ghosted(failed))
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)), {str(failed)})  # 실패한 창의 기록만 남음

        self.assertTrue(fresh.restore(failed))  # 다음 시도에서 복구
        self.assertFalse(os.path.exists(self.record))

    def test_corrupt_record_is_discarded(self):
        os.makedirs(self.state_dir)
        with open(self.record, "w", encoding="utf-8") as f:
            f.write("{ not json")
        self.assertEqual(self.guard().recover_from_file(), 0)
        self.assertFalse(os.path.exists(self.record))

    def test_restore_all_continues_after_error(self):
        other = self.make_window()
        g = self.guard()
        self.assertTrue(g.set_ghost(self.hwnd, True))
        self.assertTrue(g.set_ghost(other, True))

        real_restore, calls = g.restore, []

        def flaky(hwnd):
            calls.append(hwnd)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return real_restore(hwnd)

        with mock.patch.object(g, "restore", side_effect=flaky):
            g.restore_all()
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum(is_ghosted(h) for h in (self.hwnd, other)), 1)  # 실패한 창만 남음

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
