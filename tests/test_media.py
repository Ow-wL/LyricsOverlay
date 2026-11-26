"""재생 명령: 멜론 세션에만 한 번 보내기, 실패 후 다시 시도, 버튼은 미디어 키를 직접 보내지 않음."""

import asyncio
import unittest
from unittest import mock

from tests import _qt  # noqa: F401
import core.media_session as ms


class _Async:
    def __init__(self, value):
        self.value = value

    def __await__(self):
        if False:
            yield
        return self.value


class FakeSession:
    def __init__(self, app_id="Melon.exe"):
        self.source_app_user_model_id = app_id
        self.calls = []

    def try_skip_previous_async(self):
        self.calls.append("prev")
        return _Async(True)

    def try_skip_next_async(self):
        self.calls.append("next")
        return _Async(True)

    def try_toggle_play_pause_async(self):
        self.calls.append("play_pause")
        return _Async(True)


class FakeManager:
    def __init__(self, sessions):
        self.sessions = sessions

    def get_sessions(self):
        return self.sessions


def run(coro):
    return asyncio.run(coro)


class ControlTest(unittest.TestCase):
    def make(self, sessions):
        m = ms.MelonMediaSession()
        m._manager = FakeManager(sessions)
        return m

    def test_command_goes_only_to_melon_once(self):
        other, melon = FakeSession("Spotify.exe"), FakeSession("Melon.exe")
        m = self.make([other, melon])
        with mock.patch.object(ms, "_Manager", object()):
            for action in ("prev", "play_pause", "next"):
                self.assertTrue(run(m.control(action)))
        self.assertEqual(melon.calls, ["prev", "play_pause", "next"])
        self.assertEqual(other.calls, [])

    def test_no_melon_session_means_fallback(self):
        m = self.make([FakeSession("Spotify.exe")])
        with mock.patch.object(ms, "_Manager", object()):
            self.assertFalse(run(m.control("prev")))

    def test_poll_failure_retries_later(self):
        m = ms.MelonMediaSession()

        class Broken:
            def get_sessions(self):
                raise OSError("boom")

        m._manager = Broken()
        with mock.patch.object(ms, "_Manager", object()):
            self.assertFalse(run(m.poll()).available)
            self.assertGreater(m._retry_at, 0)
            m._retry_at = 0  # 시간이 지났다고 치면
            m._manager = FakeManager([])
            run(m.poll())  # 다시 시도해도 예외 없이 동작
        self.assertIsNotNone(m._manager)


class MelonWindowCommandTest(unittest.TestCase):
    def test_sends_appcommand_to_melon_window(self):
        import core.melon_control as mc

        sent = []
        fake_send = mock.Mock(side_effect=lambda h, m, w, l, *a: sent.append((h.value, m, l.value)) or 1)
        with mock.patch.object(mc, "find_control_window", return_value=1234), \
                mock.patch.object(mc.ctypes.windll.user32, "SendMessageTimeoutW", fake_send):
            self.assertTrue(mc.send_app_command("prev"))
            self.assertFalse(mc.send_app_command("rewind"))  # 모르는 명령
        self.assertEqual(sent, [(1234, mc.WM_APPCOMMAND, 12 << 16)])

    def test_no_melon_window(self):
        import core.melon_control as mc

        with mock.patch.object(mc, "find_control_window", return_value=None):
            self.assertFalse(mc.send_app_command("next"))


class HotkeyRepeatTest(unittest.TestCase):
    def test_held_key_runs_once_until_released(self):
        from core.hotkey_manager import _OncePerPress

        calls = []
        once = _OncePerPress(lambda: calls.append(1))
        for _ in range(13):  # 키를 누르고 있는 동안 들어오는 자동 반복
            once()
        self.assertEqual(len(calls), 1)
        once.rearm()  # 키를 뗌
        once()
        self.assertEqual(len(calls), 2)


class ButtonTest(unittest.TestCase):
    def test_buttons_emit_without_sending_keys(self):
        from PySide6.QtWidgets import QApplication, QPushButton  # type: ignore

        QApplication.instance() or QApplication([])
        from gui.widgets.media_controls import MediaControls

        with mock.patch("core.hotkey_manager._send_media_key") as send:
            mc = MediaControls("app")
            got = []
            mc.action_triggered.connect(got.append)
            for b in mc.findChildren(QPushButton):
                b.click()
        self.assertEqual(got, ["prev", "play_pause", "next"])
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
