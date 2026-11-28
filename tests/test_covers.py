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
from main import is_song_title, link_song


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
            self.assertEqual(s.backfill(history), (1, 0))
            self.assertEqual(s._jobs.qsize(), 1)
            self.assertEqual(s.backfill(history), (0, 0))  # 이미 예약됨
            s._finish(cv._key("곡", "가수"), counted=True)  # 작업이 끝나면 예약 표시가 풀림
            self.assertNotIn(cv._key("곡", "가수"), s._queued)
            self.assertEqual(s.backfill_left, 0)

    def test_backfill_is_capped_and_starts_with_recent_songs(self):
        """한 번에 정해진 곡 수까지만, 목록 앞쪽(최근 곡)부터 예약합니다. 남은 곡 수를 알려 줍니다."""
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            history = [{"title": f"곡{i}", "artist": "가수"} for i in range(cv.BACKFILL_MAX_PER_RUN + 7)]
            self.assertEqual(s.backfill(history), (cv.BACKFILL_MAX_PER_RUN, 7))
            queued = [s._jobs.get_nowait()[2] for _ in range(s._jobs.qsize())]
            self.assertEqual(queued, [f"곡{i}" for i in range(cv.BACKFILL_MAX_PER_RUN)])
            self.assertEqual(s.backfill_left, cv.BACKFILL_MAX_PER_RUN)

    def test_backfill_waits_between_runs(self):
        """연달아 눌러도 대기 시간이 지나기 전에는 더 예약하지 않습니다 (요청이 몰리지 않게)."""
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            history = [{"title": f"곡{i}", "artist": "가수"} for i in range(5)]
            self.assertEqual(s.backfill_wait(), 0)
            self.assertEqual(s.backfill(history, limit=2), (2, 3))
            self.assertGreater(s.backfill_wait(), cv.BACKFILL_COOLDOWN_SEC - 5)
            self.assertEqual(s.backfill(history, limit=2), (0, 3))  # 아직 대기 중
            self.assertEqual(s._jobs.qsize(), 2)

            with mock.patch.object(cv.time, "monotonic", return_value=time.monotonic() + cv.BACKFILL_COOLDOWN_SEC + 1):
                self.assertEqual(s.backfill_wait(), 0)
                self.assertEqual(s.backfill(history, limit=2), (2, 1))

    def test_backfill_with_nothing_to_do_does_not_start_cooldown(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            self.assertEqual(s.backfill([{"title": "멜론 PC 플레이어", "artist": "Unknown"}]), (0, 0))
            self.assertEqual(s.backfill_wait(), 0)

    def test_disabled_store_does_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            s.enabled = False
            s.remember("a", "b", "12345", "https://cdnimg.melon.co.kr/a.jpg")
            self.assertEqual(s.backfill([{"title": "곡", "artist": "가수"}]), (0, 0))
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


class LinkSongTest(unittest.TestCase):
    """곡 ID는 먼저, 커버 주소는 조금 뒤에 알게 됩니다. 커버 주소가 올 때까지 계속 확인해야 합니다."""

    class Searcher:
        def __init__(self):
            self.ids, self.covers = {}, {}

        def song_id_for(self, title):
            return self.ids.get(title)

        def cover_for(self, title):
            return self.covers.get(title)

    def test_cover_arrives_after_song_id(self):
        s, info = self.Searcher(), {"title": "감사", "artist": "김동률"}
        self.assertEqual(link_song(info, s, "감사 - 김동률"), (False, None))  # 검색 중
        self.assertNotIn("song_id", info)

        s.ids["감사 - 김동률"] = "3897927"  # 검색은 끝났고 곡 페이지는 아직
        self.assertEqual(link_song(info, s, "감사 - 김동률"), (True, None))
        self.assertEqual(info["song_id"], "3897927")

        url = "https://cdnimg.melon.co.kr/a_500.jpg"
        s.covers["감사 - 김동률"] = url  # 곡 페이지까지 받음
        self.assertEqual(link_song(info, s, "감사 - 김동률"), (False, url))  # 곡 ID를 붙인 뒤에도 커버를 돌려줌

    def test_ignores_result_for_another_song(self):
        s, info = self.Searcher(), {"title": "감사", "artist": "김동률"}
        s.ids["취중진담 - 김동률"] = "1590160"
        s.covers["취중진담 - 김동률"] = "https://cdnimg.melon.co.kr/b_500.jpg"
        self.assertEqual(link_song(info, s, "취중진담 - 김동률"), (False, None))  # 창 제목이 이미 다음 곡
        self.assertNotIn("song_id", info)


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
