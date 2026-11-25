from rapidfuzz import fuzz, process  # type: ignore

from lyrics.searcher import LyricsSearcher

# OCR 결과가 이 글자 수 이하이면 매핑을 시도하지 않고 원문 반환
_MIN_OCR_LEN = 3

# 후보 가사 길이가 OCR 길이의 이 비율 미만이면 후보에서 제외 (너무 짧은 후보 차단)
_CANDIDATE_LEN_RATIO = 0.6

# 이 점수 미만이면 가사와 맞지 않는 것으로 보고 OCR 원문을 그대로 씁니다.
_SCORE_CUTOFF = 60

# 최고 점수와 이만큼 차이 안에 있는 후보들은 '비슷하게 맞는 줄'로 보고,
# 그중 곡 안에서 지금 위치에 가까운 줄을 고릅니다. (후렴처럼 비슷한 줄이 여러 번 나올 때)
_POSITION_WINDOW = 8


def line_score(a: str, b: str, **_kwargs) -> float:
    """가사 한 줄끼리 비교 점수 (0~100).

    WRatio는 짧은 OCR 줄을 단어 하나만 겹치는 다른 줄과도 높게 쳐서(예: 85점),
    전체 일치(ratio)와 OCR이 줄 일부만 읽은 경우(partial_ratio, 약간 감점) 중 큰 값을 씁니다.
    """
    return max(fuzz.ratio(a, b), fuzz.partial_ratio(a, b) * 0.9)


class LyricMatcher:
    """OCR 결과를 실제 가사와 퍼지 매칭하여 정답 문장을 반환합니다.

    줄마다 따로 비교하면 비슷한 다른 부분의 가사로 바뀔 수 있어서,
    마지막으로 맞춘 줄 번호를 기억해 두고 그 근처(현재 줄은 그대로이거나 다음,
    다음 줄은 현재 줄 + 1)를 우선합니다.
    """

    def __init__(self):
        self.searcher = LyricsSearcher()
        self.last_status: str | None = None
        self.last_idx: int | None = None

    def reset_recent(self) -> None:
        """곡이 바뀔 때 호출: 위치 기억을 지웁니다."""
        self.last_idx = None

    def match_lines(self, lines: list[str], song_title: str) -> tuple[list[str], list[str]]:
        """OCR 줄 목록(현재 줄, 다음 줄 …)을 보정합니다. (보정된 줄들, 상태 메시지들)"""
        fixed: list[str] = []
        statuses: list[str] = []
        prev_idx: int | None = None
        for i, line in enumerate(lines):
            if i == 0:
                expected = self.last_idx
            else:
                expected = prev_idx + 1 if prev_idx is not None else None
            text, status, idx = self._match(line, song_title, expected, forward_only=(i == 0))
            if status:
                statuses.append(status)
            fixed.append(text)
            if i == 0 and idx is not None:
                self.last_idx = idx
            prev_idx = idx
        return fixed, statuses

    def get_best_match(self, ocr_text: str, song_title: str) -> tuple[str, str | None]:
        """(이전 API 호환) 한 줄만 보정합니다."""
        text, status, _ = self._match(ocr_text, song_title, None, False)
        return text, status

    def _match(
        self, ocr_text: str, song_title: str, expected: int | None, forward_only: bool
    ) -> tuple[str, str | None, int | None]:
        full_lyrics, status = self.searcher.search_lyrics(song_title)
        if status:
            self.last_status = status

        if not full_lyrics:
            return ocr_text, status, None

        ocr_stripped = ocr_text.strip()

        # ── 전략 1: OCR 결과가 너무 짧으면 매핑하지 않음 ──────────────────
        if len(ocr_stripped) <= _MIN_OCR_LEN:
            return ocr_text, status, None

        # ── 전략 2: 후보 가사 중 OCR보다 현저히 짧은 것 제외 ───────────────
        min_len = max(1, int(len(ocr_stripped) * _CANDIDATE_LEN_RATIO))
        pool = {i: ln for i, ln in enumerate(full_lyrics) if len(ln.strip()) >= min_len}
        if not pool:
            pool = dict(enumerate(full_lyrics))

        matches = process.extract(
            ocr_stripped, pool, scorer=line_score, score_cutoff=_SCORE_CUTOFF, limit=12
        )
        if not matches:
            return ocr_text, status, None

        # ── 전략 3: 비슷하게 맞는 줄이 여럿이면 지금 위치에 가까운 줄 ────────
        best_score = matches[0][1]
        close = [(text, score, idx) for text, score, idx in matches if score >= best_score - _POSITION_WINDOW]
        if expected is not None and len(close) > 1:
            def distance(item) -> float:
                idx = item[2]
                d = idx - expected
                if forward_only and d < 0:
                    d = abs(d) + 1000  # 현재 줄은 보통 앞으로만 진행 (뒤로 가는 건 최후의 선택)
                return abs(d) - item[1] / 1000  # 거리가 같으면 점수가 높은 쪽
            close.sort(key=distance)
        text, _score, idx = close[0]
        return text, status, idx
