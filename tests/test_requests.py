"""멜론 요청 줄이기(검색 생략·다시 듣는 곡·연속 실패 시 쉬기)와 진단 로그."""

import os
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests import _qt  # noqa: F401  (경로 설정)
from core import app_log, melon_http
import core.covers as cv
from lyrics.searcher import LyricsSearcher

COVER = "https://cdnimg.melon.co.kr/cm/album/images/000/00/001/1_500.jpg"
SEARCH = "https://www.melon.com/search/song/index.htm"
DETAIL = "https://www.melon.com/song/detail.htm?songId="


def detail_page(lines=("첫 줄", "둘째 줄", "셋째 줄", "넷째 줄"), cover=COVER) -> str:
    meta = f'<meta property="og:image" content="{cover}">' if cover else ""
    body = "<br>".join(lines)
    return f'<html><head>{meta}</head><body><div id="d_video_summary">{body}</div></body></html>'


def search_page(song_id="1234567", title="곡", artist="가수") -> str:
    return (
        '<div class="tb_list"><table><tbody><tr>'
        f'<td><a class="fc_gray" href="javascript:melon.link.goSongDetail(\'{song_id}\');">{title}</a></td>'
        f'<td><div id="artistName"><a class="fc_mgray">{artist}</a></div></td>'
        "</tr></tbody></table></div>"
    )


class Pages:
    """요청한 주소를 기록하고, 주소에 맞는 페이지를 돌려주는 가짜 멜론."""

    def __init__(self, details: dict, search: str = ""):
        self.details, self.search, self.calls = details, search, []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        if url.startswith(SEARCH):
            return self.search
        page = self.details[url.split("songId=")[1]]
        if isinstance(page, Exception):
            raise page
        return page

    def kinds(self) -> list[str]:
        return ["search" if u.startswith(SEARCH) else "detail:" + u.split("songId=")[1] for u in self.calls]


def make_searcher(pages: Pages) -> LyricsSearcher:
    s = LyricsSearcher()
    s.shutdown()
    s._get_text = pages
    return s


class SkipSearchTest(unittest.TestCase):
    def test_known_song_needs_only_the_song_page(self):
        pages = Pages({"1234567": detail_page()})
        s = make_searcher(pages)
        s.id_lookup = lambda name: "1234567" if name == "곡 - 가수" else None
        lines, status, retry = s._fetch("곡 - 가수", "곡 - 가수")
        self.assertEqual(pages.kinds(), ["detail:1234567"])  # 검색 요청 없음
        self.assertEqual(len(lines), 4)
        self.assertFalse(retry)
        self.assertEqual(s.song_id_for("곡 - 가수"), "1234567")
        self.assertEqual(s.cover_for("곡 - 가수"), COVER)

    def test_unknown_song_searches_then_loads(self):
        pages = Pages({"1234567": detail_page()}, search_page())
        s = make_searcher(pages)
        lines, _status, _retry = s._fetch("곡 - 가수", "곡 - 가수")
        self.assertEqual(pages.kinds(), ["search", "detail:1234567"])
        self.assertEqual(len(lines), 4)

    def test_stale_id_falls_back_to_search(self):
        """알고 있던 곡 ID가 더는 맞지 않으면(오류·가사 없음) 검색해서 새 ID로 받습니다."""
        pages = Pages({"1111111": RuntimeError("404"), "1234567": detail_page()}, search_page())
        s = make_searcher(pages)
        s.id_lookup = lambda name: "1111111"
        lines, _status, _retry = s._fetch("곡 - 가수", "곡 - 가수")
        self.assertEqual(pages.kinds(), ["detail:1111111", "search", "detail:1234567"])
        self.assertEqual(len(lines), 4)
        self.assertEqual(s.song_id_for("곡 - 가수"), "1234567")

    def test_song_without_lyrics_is_not_fetched_twice(self):
        pages = Pages({"1234567": detail_page(lines=())}, search_page())
        s = make_searcher(pages)
        s.id_lookup = lambda name: "1234567"
        lines, status, retry = s._fetch("곡 - 가수", "곡 - 가수")
        self.assertEqual(pages.kinds(), ["detail:1234567", "search"])  # 같은 곡 페이지를 다시 받지 않음
        self.assertEqual(lines, [])
        self.assertFalse(retry)
        self.assertIn("가사 데이터 없음", status)

    def test_bad_lookup_value_is_ignored(self):
        pages = Pages({"1234567": detail_page()}, search_page())
        s = make_searcher(pages)
        s.id_lookup = lambda name: "../../x"
        s._fetch("곡 - 가수", "곡 - 가수")
        self.assertEqual(pages.kinds(), ["search", "detail:1234567"])

    def test_pause_is_not_swallowed_by_fallback(self):
        pages = Pages({"1234567": melon_http.MelonPaused("쉬는 중")}, search_page())
        s = make_searcher(pages)
        s.id_lookup = lambda name: "1234567"
        lines, status, retry = s._fetch("곡 - 가수", "곡 - 가수")
        self.assertEqual(pages.kinds(), ["detail:1234567"])  # 쉬는 중이면 검색으로 넘어가지 않음
        self.assertTrue(retry)
        self.assertIn("쉬는 중", status)


class ReplayCacheTest(unittest.TestCase):
    def test_song_heard_again_makes_no_request(self):
        pages = Pages({"1234567": detail_page()}, search_page())
        s = make_searcher(pages)
        s._remember("곡 - 가수", ["a", "b", "c"])
        submitted = []
        s._executor = mock.Mock(submit=lambda *a, **k: submitted.append(a))

        s.search_lyrics("다른 곡 - 가수")  # 다른 곡으로 넘어갔다가
        self.assertEqual(len(submitted), 1)
        lines, status = s.search_lyrics("곡 - 가수")  # 다시 들음
        self.assertEqual(lines, ["a", "b", "c"])
        self.assertIn("요청 없음", status)
        self.assertEqual(len(submitted), 1)  # 새 검색을 맡기지 않음

    def test_cache_is_bounded(self):
        s = make_searcher(Pages({}))
        from lyrics import searcher as mod
        for i in range(mod._CACHE_SONGS + 5):
            s._remember(f"곡{i} - 가수", ["a"])
        self.assertEqual(len(s._cache), mod._CACHE_SONGS)
        self.assertIsNone(s._cached("곡0 - 가수"))  # 오래된 것부터 버림
        self.assertIsNotNone(s._cached(f"곡{mod._CACHE_SONGS + 4} - 가수"))


class FailurePauseTest(unittest.TestCase):
    def setUp(self):
        melon_http._reset_for_tests()
        self.addCleanup(melon_http._reset_for_tests)

    def test_repeated_failures_pause_requests(self):
        for _ in range(melon_http.FAIL_LIMIT - 1):
            melon_http.report_status(500)
        self.assertEqual(melon_http.paused_for(), 0)
        melon_http.report_error()  # 응답 없음도 실패로 셈
        self.assertGreater(melon_http.paused_for(), melon_http.FAIL_PAUSE_SEC - 5)
        self.assertEqual(melon_http.pause_reason(), melon_http.ERRORS)
        self.assertIn("계속 실패", melon_http.pause_text())
        with self.assertRaises(melon_http.MelonPaused):
            melon_http.wait_turn()

    def test_success_resets_the_streak(self):
        for _ in range(melon_http.FAIL_LIMIT - 1):
            melon_http.report_status(404)
        melon_http.report_status(200)
        melon_http.report_status(404)
        self.assertEqual(melon_http.paused_for(), 0)

    def test_refusal_reason_and_text(self):
        melon_http.report_status(429)
        self.assertEqual(melon_http.pause_reason(), melon_http.REFUSED)
        self.assertIn("거절", melon_http.pause_text())

    def test_pause_survives_restart(self):
        melon_http.report_status(429)
        until = melon_http.paused_until_epoch()
        self.assertGreater(until, time.time() + 60)

        melon_http._reset_for_tests()  # 앱을 다시 켠 것처럼
        self.assertEqual(melon_http.paused_for(), 0)
        melon_http.restore_pause(until, melon_http.REFUSED)
        self.assertGreater(melon_http.paused_for(), 60)
        self.assertEqual(melon_http.pause_reason(), melon_http.REFUSED)

    def test_old_or_bad_saved_pause_is_ignored(self):
        melon_http.restore_pause(time.time() - 10)
        melon_http.restore_pause("nonsense")
        melon_http.restore_pause(None)
        self.assertEqual(melon_http.paused_for(), 0)
        self.assertEqual(melon_http.paused_until_epoch(), 0)

    def test_restored_pause_is_capped(self):
        melon_http.restore_pause(time.time() + 10 * 24 * 3600)  # 시계가 틀렸거나 값이 망가진 경우
        self.assertLessEqual(melon_http.paused_for(), melon_http.BLOCK_PAUSE_SEC)


class AutoBackfillTest(unittest.TestCase):
    def make(self, d):
        with mock.patch.object(cv.threading.Thread, "start"):
            return cv.CoverStore(d)

    def setUp(self):
        melon_http._reset_for_tests()
        self.addCleanup(melon_http._reset_for_tests)
        self.history = [{"title": f"곡{i}", "artist": "가수"} for i in range(4)]

    @staticmethod
    def done(store, title: str) -> None:
        """작업 스레드가 그 곡을 처리하고 끝낸 상태로 만듭니다 (여기서는 '못 찾음'으로 기록)."""
        key = cv._key(title, "가수")
        store._mark_miss(key)
        store._finish(key, counted=True)

    def test_one_song_at_a_time_without_cooldown(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            self.assertEqual(s.backfill(self.history, limit=1, auto=True), (1, 3))
            self.assertEqual(s.backfill_wait(), 0)  # 자동 채우기는 버튼의 대기 시간을 시작하지 않음
            self.assertEqual(s.backfill(self.history, limit=1, auto=True), (0, 0))  # 앞의 것이 끝날 때까지 기다림
            self.done(s, "곡0")
            self.assertEqual(s.backfill(self.history, limit=1, auto=True), (1, 2))

    def test_ignores_button_cooldown_but_not_melon_pause(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            self.assertEqual(s.backfill(self.history, limit=1), (1, 3))  # 버튼으로 한 번
            self.done(s, "곡0")
            self.assertGreater(s.backfill_wait(), 0)
            self.assertEqual(s.backfill(self.history, limit=1, auto=True), (1, 2))
            self.done(s, "곡1")

            melon_http.report_status(429)
            self.assertEqual(s.backfill(self.history, limit=1, auto=True), (0, 2))

    def test_song_id_lookup_from_cover_index(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.make(d)
            s.remember("곡", "가수", "1234567", COVER)
            self.assertEqual(s.song_id_for("곡", "가수"), "1234567")
            self.assertIsNone(s.song_id_for("모르는 곡", "가수"))
            s._index[cv._key("못 찾은 곡", "가수")] = {"miss": time.time()}
            self.assertIsNone(s.song_id_for("못 찾은 곡", "가수"))


class AppLogTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(app_log.stop)
        self.enabled = True
        self.path = app_log.start(should_log=lambda: self.enabled, directory=self._tmp.name)

    def read(self) -> str:
        sys.stdout.flush()
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_messages_prints_and_errors_are_kept(self):
        app_log.write("새로운 곡 감지: 곡 - 가수")
        print("[⚠️] 무언가 실패했습니다")
        print("오류 내용", file=sys.stderr)
        text = self.read()
        self.assertIn("=== 시작: Lyrics Overlay", text)
        self.assertIn("새로운 곡 감지: 곡 - 가수", text)
        self.assertIn("[⚠️] 무언가 실패했습니다", text)
        self.assertIn("[stderr] 오류 내용", text)

    def test_lyrics_on_console_do_not_reach_the_file(self):
        app_log.console("🔥 현재: 파일에 남으면 안 되는 가사 한 줄")
        self.assertNotIn("남으면 안 되는", self.read())

    def test_nothing_written_while_turned_off(self):
        self.enabled = False
        app_log.write("새로운 곡 감지: 비밀 곡 - 가수")
        print("[DEBUG] 찾은 곡 ID: 1 (비밀 곡 - 가수)")
        self.assertNotIn("비밀 곡", self.read())

    def test_stop_restores_streams(self):
        self.assertIsInstance(sys.stdout, app_log._Tee)
        app_log.stop()
        self.assertNotIsInstance(sys.stdout, app_log._Tee)
        self.assertNotIsInstance(sys.stderr, app_log._Tee)
        self.assertIsNone(app_log.current_path())

    def test_works_without_a_console(self):
        """창 모드 exe에는 stdout이 없습니다(None). 그래도 print가 로그로 가고 오류가 나지 않아야 합니다."""
        app_log.stop()
        with mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None):
            path = app_log.start(directory=os.path.join(self._tmp.name, "noconsole"))
            print("[DEBUG] 콘솔 없이 찍은 줄")
            app_log.console("🔥 현재: 가사")
            self.assertFalse(sys.stdout.isatty())
            app_log.stop()
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("콘솔 없이 찍은 줄", text)
        self.assertNotIn("가사", text)


if __name__ == "__main__":
    unittest.main()
