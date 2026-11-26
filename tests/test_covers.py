"""앨범 커버 저장소와 '곡이 아닌 창 제목' 거르기."""

import os
import tempfile
import time
import unittest
from unittest import mock

from tests import _qt  # noqa: F401
import core.covers as cv
from gui.pages.stats_page import _artist_rows, _song_rows
from lyrics.searcher import cover_url_from_detail
from main import is_song_title


class FakeSoup:
    def __init__(self, url):
        self.url = url

    def select_one(self, _sel):
        return None if self.url is None else {"content": self.url}


class CoverUrlTest(unittest.TestCase):
    def test_only_melon_image_server(self):
        ok = "https://cdnimg.melon.co.kr/cm/album/images/003/46/951/346951_500.jpg"
        self.assertEqual(cover_url_from_detail(FakeSoup(ok)), ok)
        self.assertIsNone(cover_url_from_detail(FakeSoup("https://evil.example.com/a.jpg")))
        self.assertIsNone(cover_url_from_detail(FakeSoup("https://cdnimg.melon.co.kr/x.exe")))
        self.assertIsNone(cover_url_from_detail(FakeSoup(None)))


class CoverStoreTest(unittest.TestCase):
    def make(self, d):
        with mock.patch.object(cv.threading.Thread, "start"):  # 작업 스레드는 띄우지 않음
            return cv.CoverStore(d)

    def test_path_found_by_song_id_or_title(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            os.makedirs(s.dir)
            open(os.path.join(s.dir, "30244931.jpg"), "wb").close()
            self.assertTrue(s.path_for("x", "y", "30244931").endswith("30244931.jpg"))
            s.remember("봄날", "방탄소년단", "30244931", "https://cdnimg.melon.co.kr/a_500.jpg")
            self.assertIsNotNone(s.path_for("봄날", "방탄소년단"))  # 곡 ID 없는 예전 기록도 제목으로

    def test_bad_inputs_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            s.remember("a", "b", "../../x", "https://cdnimg.melon.co.kr/a.jpg")
            s.remember("a", "b", "12345", "https://evil.example.com/a.jpg")
            self.assertTrue(s._jobs.empty())
            self.assertIsNone(s.path_for("곡", "Unknown"))  # 가수를 모르면 찾지 않음
            self.assertTrue(s._jobs.empty())

    def test_no_automatic_backfill(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            s.path_for("곡", "가수")  # 화면에 보이기만 해서는 멜론에 요청하지 않음
            self.assertTrue(s._jobs.empty())

    def test_backfill_only_on_request_once_per_song(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            history = [{"title": "곡", "artist": "가수"}, {"title": "곡", "artist": "가수"},
                       {"title": "곡2", "artist": "가수"}, {"title": "멜론 PC 플레이어", "artist": "Unknown"}]
            s._index[cv._key("곡2", "가수")] = {"miss": time.time()}  # 최근에 못 찾은 곡
            self.assertEqual(s.backfill(history), 1)
            self.assertEqual(s._jobs.qsize(), 1)
            self.assertEqual(s.backfill(history), 0)  # 이미 예약됨
            s._finish(cv._key("곡", "가수"), counted=True)  # 작업이 끝나면 예약 표시가 풀림
            self.assertNotIn(cv._key("곡", "가수"), s._queued)
            self.assertEqual(s.backfill_left, 0)

    def test_disabled_store_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            s.enabled = False
            s.remember("a", "b", "12345", "https://cdnimg.melon.co.kr/a.jpg")
            self.assertEqual(s.backfill([{"title": "곡", "artist": "가수"}]), 0)
            self.assertTrue(s._jobs.empty())

    def test_clear_removes_files_and_queue(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            os.makedirs(s.dir)
            open(os.path.join(s.dir, "12345.jpg"), "wb").close()
            s.backfill([{"title": "곡", "artist": "가수"}])
            self.assertEqual(s.clear(), 1)
            self.assertEqual(s.file_count(), 0)
            self.assertTrue(s._jobs.empty())


class MelonHttpTest(unittest.TestCase):
    def tearDown(self):
        from core import melon_http
        melon_http._reset_for_tests()

    def test_honest_user_agent(self):
        from core import melon_http
        from lyrics.searcher import LyricsSearcher

        s = LyricsSearcher()
        s.shutdown()
        self.assertTrue(s.headers["User-Agent"].startswith("LyricsOverlay/"))
        self.assertNotIn("Mozilla", s.headers["User-Agent"])
        self.assertNotIn("Referer", s.headers)
        self.assertEqual(s.headers["User-Agent"], melon_http.USER_AGENT)

    def test_refusal_pauses_all_requests(self):
        from core import melon_http

        melon_http.report_status(200)
        melon_http.wait_turn()  # 정상
        melon_http.report_status(429)
        self.assertGreater(melon_http.paused_for(), 60)
        with self.assertRaises(melon_http.MelonPaused):
            melon_http.wait_turn()

    def test_disabled_searcher_makes_no_request(self):
        from lyrics.searcher import LyricsSearcher

        s = LyricsSearcher()
        s.shutdown()
        s.enabled = False
        with mock.patch.object(s, "_get_text", side_effect=AssertionError("요청하면 안 됨")):
            self.assertEqual(s.search_lyrics("곡 - 가수"), ([], None))


class SongTitleTest(unittest.TestCase):
    def test_non_song_window_titles(self):
        self.assertFalse(is_song_title("멜론 PC 플레이어"))
        self.assertFalse(is_song_title(" - 가수"))
        self.assertTrue(is_song_title("감사 - 김동률"))
        self.assertTrue(is_song_title("A - B - 가수"))

    def test_rankings_skip_non_songs_and_carry_cover_info(self):
        history = [{"title": "멜론 PC 플레이어", "artist": "Unknown"}] * 3 + [
            {"title": "감사", "artist": "김동률", "song_id": "3897927"},
            {"title": "감사", "artist": "김동률"},
            {"title": "취중진담", "artist": "김동률"},
        ]
        songs = _song_rows(history)
        self.assertEqual([r[0] for r in songs], ["감사", "취중진담"])
        self.assertEqual(songs[0][3]["song_id"], "3897927")
        artists = _artist_rows(history)
        self.assertEqual(artists[0][:3], ("김동률", "", 3))
        self.assertEqual(artists[0][3]["title"], "감사")  # 가수 칸은 가장 많이 들은 곡의 커버
        self.assertTrue(artists[0][3]["circle"])


if __name__ == "__main__":
    unittest.main()
