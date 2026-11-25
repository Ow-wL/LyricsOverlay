"""가사 검색 결과 고르기와 OCR 줄 매칭."""

import unittest

from tests import _qt  # noqa: F401  (경로 설정)
from lyrics.matcher import LyricMatcher, line_score
from lyrics.searcher import pick_best_row, score_row, split_title

LYRICS = [
    "첫 번째 줄 가사입니다",
    "두 번째 줄이 이어져요",
    "우리 함께 걸어가요 오늘 밤",
    "후렴 바로 앞 줄입니다",
    "세 번째 절 시작 부분",
    "네 번째 줄 가사예요",
    "우리 함께 걸어가요 내일 밤",
    "마지막 줄입니다",
]


def make_matcher() -> LyricMatcher:
    m = LyricMatcher()
    m.searcher.shutdown()
    m.searcher.search_lyrics = lambda q: (LYRICS, None)
    return m


class SearchResultTest(unittest.TestCase):
    def test_split_title_uses_last_dash(self):
        self.assertEqual(split_title("A - B - 가수"), ("A - B", "가수"))
        self.assertEqual(split_title("제목만"), ("", "제목만"))

    def test_prefers_exact_title_and_artist(self):
        rows = [("1", "봄날 - Live", "방탄소년단"), ("2", "봄날", "방탄소년단"), ("3", "봄날", "다른 가수")]
        best, score = pick_best_row(rows, "봄날", "방탄소년단")
        self.assertEqual(best[0], "2")
        self.assertEqual(score, 100)

    def test_ignores_bracket_suffix(self):
        best, _ = pick_best_row([("5", "밤편지", "아이유")], "밤편지 (Feat. X)", "아이유")
        self.assertEqual(best[0], "5")

    def test_rejects_unrelated_result(self):
        best, score = pick_best_row([("9", "완전히 다른 노래", "누군가")], "봄날", "방탄소년단")
        self.assertIsNone(best)
        self.assertLess(score, 70)

    def test_live_version_scores_lower(self):
        self.assertLess(score_row("봄날", "방탄소년단", "봄날 Live", "방탄소년단"),
                        score_row("봄날", "방탄소년단", "봄날", "방탄소년단"))


class MatcherTest(unittest.TestCase):
    def test_line_score_does_not_overrate_one_shared_word(self):
        self.assertGreater(line_score("마지막 줄", "마지막 줄입니다"), 85)
        self.assertLess(line_score("마지막 줄", "네 번째 줄 가사예요"), 60)

    def test_fixes_ocr_typo(self):
        fixed, _ = make_matcher().match_lines(["두 번째 줄이 이어저요"], "곡 - 가수")
        self.assertEqual(fixed, ["두 번째 줄이 이어져요"])

    def test_prefers_line_near_current_position(self):
        m = make_matcher()
        m.last_idx = 5  # 네 번째 줄 다음 → 두 번째 후렴이 와야 함
        fixed, _ = m.match_lines(["우리 함께 걸어가요 오 밤", "마지막 줄"], "곡 - 가수")
        self.assertEqual(fixed, ["우리 함께 걸어가요 내일 밤", "마지막 줄입니다"])
        self.assertEqual(m.last_idx, 6)

    def test_exact_text_wins_over_position(self):
        m = make_matcher()
        m.last_idx = 5
        fixed, _ = m.match_lines(["우리 함께 걸어가요 오늘 밤"], "곡 - 가수")
        self.assertEqual(fixed, ["우리 함께 걸어가요 오늘 밤"])

    def test_keeps_ocr_text_when_nothing_matches(self):
        fixed, _ = make_matcher().match_lines(["전혀 상관없는 글자", "ab"], "곡 - 가수")
        self.assertEqual(fixed, ["전혀 상관없는 글자", "ab"])

    def test_reset_forgets_position(self):
        m = make_matcher()
        m.last_idx = 3
        m.reset_recent()
        self.assertIsNone(m.last_idx)


if __name__ == "__main__":
    unittest.main()
