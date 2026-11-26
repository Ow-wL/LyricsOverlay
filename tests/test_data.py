"""설정·통계 파일 검증, 데이터 경로 변경, 재생 상태 판정, 단축키 규칙."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from tests import _qt  # noqa: F401
import core.stats_manager as sm
from core.app_config import AppConfig
from core.hotkey_manager import is_typing_hotkey
from core.media_session import MediaState, is_restart
from gui.widgets.hotkey_edit import pretty_hotkey
from main import recognition_idle_reason
from overlay.config_manager import DEFAULT_ROI, OverlayConfigManager, sanitize_preset


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class StatsTest(unittest.TestCase):
    def test_bad_entries_dropped_and_fields_defaulted(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, "lyrics_stats.json"), {
                "play_history": [{"title": "a", "artist": 3, "timestamp": 5}, "junk", {"x": 1}],
                "total_lines": "x", "theme": "pink",
            })
            stats = sm.load_stats(d)
        self.assertEqual(len(stats["play_history"]), 1)
        entry = stats["play_history"][0]
        self.assertEqual((entry["artist"], entry["play_time_sec"]), ("Unknown", 0))
        self.assertEqual((stats["total_lines"], stats["theme"]), (0, "light"))

    def test_song_id_kept_only_when_numeric(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, "lyrics_stats.json"), {"play_history": [
                {"title": "a", "song_id": "30244931"}, {"title": "b", "song_id": "../x"}]})
            hist = sm.load_stats(d)["play_history"]
        self.assertEqual(hist[0]["song_id"], "30244931")
        self.assertNotIn("song_id", hist[1])

    def test_corrupt_file_is_kept_aside(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, "lyrics_stats.json"), [1, 2])
            stats = sm.load_stats(d)
            backups = [f for f in os.listdir(d) if ".corrupt-" in f]
        self.assertEqual(stats["play_history"], [])
        self.assertEqual(len(backups), 1)

    def test_save_reports_success_and_block(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(sm.save_stats({"play_history": []}, d))
            path = os.path.abspath(os.path.join(d, "lyrics_stats.json"))
            sm._save_blocked.add(path)
            try:
                self.assertFalse(sm.save_stats({"play_history": []}, d))
            finally:
                sm._save_blocked.discard(path)


class OverlayConfigTest(unittest.TestCase):
    def test_invalid_values_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, "overlay_settings.json"), {
                "x": "abc", "width": 5, "font_size": "big", "bg_color": "nope",
                "text_color": "#ff0000", "ghost_mode": "yes", "hotkey_ghost": ["F9"],
                "roi": [1, 2, 3], "dashboard_view_mode": "hourly",
            })
            c = OverlayConfigManager(d)
        self.assertEqual((c.x, c.width, c.font_size), (460, 800, 22))
        self.assertEqual(c.text_color.name(), "#ff0000")
        self.assertIs(c.ghost_mode, True)
        self.assertEqual(c.hotkey_ghost, "F9")
        self.assertEqual(c.roi, DEFAULT_ROI)
        self.assertEqual(c.dashboard_view_mode, "session")

    def test_existing_users_skip_onboarding(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(OverlayConfigManager(d).onboarding_done)  # 처음 실행
            write_json(os.path.join(d, "overlay_settings.json"), {"x": 10})
            self.assertTrue(OverlayConfigManager(d).onboarding_done)   # 예전 설정 파일

    def test_legacy_quit_hotkey_migrated(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, "overlay_settings.json"), {"hotkey_quit": "Shift+Q"})
            self.assertEqual(OverlayConfigManager(d).hotkey_quit, "ctrl+alt+q")

    def test_import_adds_only_to_custom_presets(self):
        with tempfile.TemporaryDirectory() as d:
            c = OverlayConfigManager(d)
            system_before = dict(c.PRESET_STYLES)
            path = os.path.join(d, "import.json")
            write_json(path, {"system_presets": {"기본 (반투명 검정)": {"bg_color": "#123456"}},
                              "custom_presets": {"내 것": {"text_color": "#00ff00", "outline_width": 99},
                                                 "깨진 것": {"font_size": "x"}}})
            self.assertEqual(c.import_styles(path), 2)
            self.assertEqual(c.PRESET_STYLES, system_before)
            self.assertNotIn("outline_width", c.custom_presets["내 것"])  # 범위 밖 값 버림
            self.assertNotIn("깨진 것", c.custom_presets)

    def test_sanitize_preset(self):
        self.assertIsNone(sanitize_preset("not a dict"))
        self.assertEqual(sanitize_preset({"bg_alpha": 300, "font_size": 20}), {"font_size": 20})


class DataDirTest(unittest.TestCase):
    def make_config(self, data_dir):
        cfg = AppConfig.__new__(AppConfig)

        class FakeSettings:
            def setValue(self, k, v):
                self.last = (k, v)

        cfg.settings, cfg._listeners, cfg._data_dir = FakeSettings(), [], data_dir
        return cfg

    def test_existing_data_requires_confirmation_and_is_backed_up(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            cfg = self.make_config(a)
            moved = []
            cfg.add_listener(moved.append)
            write_json(os.path.join(b, "lyrics_stats.json"), {"old": 1})
            self.assertFalse(cfg.set_data_dir(b))
            self.assertEqual(cfg.data_dir, a)
            self.assertTrue(cfg.set_data_dir(b, overwrite_existing=True))
            self.assertEqual(moved, [os.path.abspath(b)])
            self.assertTrue(any(f.startswith("lyrics_stats.json.bak-") for f in os.listdir(b)))


class PlaybackTest(unittest.TestCase):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def state(self, position, start_offset):
        return MediaState(True, True, position, 200, self.t0 + timedelta(seconds=start_offset))

    def test_restart_after_listening_counts(self):
        self.assertTrue(is_restart(self.state(0, 0), self.state(0.5, 205), played_sec=190))

    def test_resume_mid_song_does_not_count(self):
        self.assertFalse(is_restart(self.state(0, 0), self.state(80, 30), played_sec=80))

    def test_early_skip_back_does_not_count(self):
        self.assertFalse(is_restart(self.state(0, 0), self.state(0.2, 40), played_sec=40))

    def test_idle_reasons(self):
        self.assertIn("일시정지", recognition_idle_reason(True, False, True, True))
        self.assertIn("오버레이", recognition_idle_reason(True, True, False, False))
        self.assertEqual(recognition_idle_reason(False, False, True, False), "")  # 상태를 모르면 계속
        self.assertEqual(recognition_idle_reason(True, True, False, True), "")    # 창에서 보고 있음


class HotkeyTest(unittest.TestCase):
    def test_typing_combos_rejected(self):
        self.assertTrue(is_typing_hotkey("q"))
        self.assertTrue(is_typing_hotkey("shift+q"))
        self.assertFalse(is_typing_hotkey("ctrl+alt+q"))
        self.assertFalse(is_typing_hotkey("F9"))

    def test_pretty(self):
        self.assertEqual(pretty_hotkey("ctrl+shift+right"), "Ctrl + Shift + →")
        self.assertEqual(pretty_hotkey(""), "없음")


if __name__ == "__main__":
    unittest.main()
