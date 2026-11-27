"""단축키 해석(RegisterHotKey), 자동 실행 등록, OCR 생략 판단, 커버 캐시 크기 제한."""

import unittest
from unittest import mock

import numpy as np

from tests import _qt  # noqa: F401
from core import autostart
from core.hotkey_manager import MOD_ALT, MOD_CONTROL, MOD_SHIFT, HotkeyManager, parse_hotkey
from main import roi_unchanged


class ParseHotkeyTest(unittest.TestCase):
    def test_common_combos(self):
        self.assertEqual(parse_hotkey("ctrl+shift+left"), (MOD_CONTROL | MOD_SHIFT, 0x25))
        self.assertEqual(parse_hotkey("F9"), (0, 0x78))
        self.assertEqual(parse_hotkey("ctrl+alt+q"), (MOD_CONTROL | MOD_ALT, ord("Q")))
        self.assertEqual(parse_hotkey("alt+page down"), (MOD_ALT, 0x22))
        self.assertEqual(parse_hotkey("ctrl+1"), (MOD_CONTROL, ord("1")))

    def test_invalid(self):
        self.assertIsNone(parse_hotkey(""))
        self.assertIsNone(parse_hotkey("ctrl+shift"))     # 일반 키 없음
        self.assertIsNone(parse_hotkey("ctrl+a+b"))       # 일반 키 둘
        self.assertIsNone(parse_hotkey("f25"))
        self.assertIsNone(parse_hotkey("ctrl+없는키"))

    def test_refresh_reports_typing_and_unparsable(self):
        mgr = HotkeyManager(lambda: None, lambda: None, on_media=lambda a: None)
        logs = []
        with mock.patch("core.hotkey_manager._HotkeyThread") as thread:
            thread.return_value.failed = []
            problems = mgr.refresh("q", "ctrl+a+b", hotkey_next="ctrl+shift+right", log_fn=logs.append)
        self.assertEqual([p[1] for p in problems], ["q", "ctrl+a+b"])
        entries = thread.call_args[0][0]
        self.assertEqual([(e[0], e[1]) for e in entries], [("다음 곡", "ctrl+shift+right")])


class AutostartTest(unittest.TestCase):
    def test_command_has_flag_and_quoted_path(self):
        cmd = autostart.command(r"C:\Program Files\LO\LyricsOverlay.exe")
        self.assertEqual(cmd, '"C:\\Program Files\\LO\\LyricsOverlay.exe" --autostart')
        self.assertTrue(autostart.launched_by_autostart(["x.exe", "--autostart"]))
        self.assertFalse(autostart.launched_by_autostart(["x.exe"]))

    def test_source_run_cannot_enable(self):
        with mock.patch.object(autostart, "supported", return_value=False), \
                mock.patch.object(autostart, "winreg") as reg:
            self.assertFalse(autostart.set_enabled(True))
            reg.SetValueEx.assert_not_called()

    def test_enable_disable_writes_run_key(self):
        reg = mock.MagicMock()
        with mock.patch.object(autostart, "winreg", reg), \
                mock.patch.object(autostart, "supported", return_value=True), \
                mock.patch.object(autostart.sys, "executable", r"C:\LO\LyricsOverlay.exe"):
            self.assertTrue(autostart.set_enabled(True))
            reg.SetValueEx.assert_called_once()
            self.assertEqual(reg.SetValueEx.call_args[0][1], "LyricsOverlay")
            self.assertIn("--autostart", reg.SetValueEx.call_args[0][4])
            self.assertTrue(autostart.set_enabled(False))
            reg.DeleteValue.assert_called_once()


class RoiUnchangedTest(unittest.TestCase):
    def test_same_and_noise_and_change(self):
        a = np.zeros((46, 251, 3), np.uint8)
        b = a.copy()
        self.assertFalse(roi_unchanged(None, a))
        self.assertTrue(roi_unchanged(a, b))
        b[0, 0] = 40  # 픽셀 하나 잡음
        self.assertTrue(roi_unchanged(a, b))
        c = a.copy()
        c[10:30, 20:200] = 255  # 가사가 바뀜
        self.assertFalse(roi_unchanged(a, c))
        self.assertFalse(roi_unchanged(a, a[:, :100]))  # 크기가 다름


class CoverCacheTest(unittest.TestCase):
    def test_lru_limits(self):
        from PySide6.QtGui import QPixmap  # type: ignore
        from PySide6.QtWidgets import QApplication  # type: ignore
        from gui.widgets import artwork

        QApplication.instance() or QApplication([])
        cache = artwork.OrderedDict()
        for i in range(10):
            artwork._put(cache, i, QPixmap(1, 1), 3)
        self.assertEqual(list(cache), [7, 8, 9])
        artwork._get(cache, 7)  # 최근에 쓴 것은 남음
        artwork._put(cache, 10, QPixmap(1, 1), 3)
        self.assertEqual(list(cache), [9, 7, 10])


if __name__ == "__main__":
    unittest.main()
