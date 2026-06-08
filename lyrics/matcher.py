from rapidfuzz import process, fuzz  # type: ignore

from lyrics.searcher import LyricsSearcher

# OCR 결과가 이 글자 수 이하이면 매핑을 시도하지 않고 원문 반환
_MIN_OCR_LEN = 3

# 후보 가사 길이가 OCR 길이의 이 비율 미만이면 후보에서 제외 (너무 짧은 후보 차단)
_CANDIDATE_LEN_RATIO = 0.6


class LyricMatcher:
    """OCR 결과를 실제 가사와 퍼지 매칭하여 정답 문장을 반환합니다."""

    def __init__(self):
        self.searcher = LyricsSearcher()
        self.last_status: str | None = None

    def reset_recent(self) -> None:
        """곡이 바뀔 때 호출 (현재는 상태 없음, 확장용으로 유지)."""
        pass

    def get_best_match(self, ocr_text: str, song_title: str) -> tuple[str, str | None]:
        """OCR 텍스트와 가사 DB를 비교해 가장 유사한 줄을 반환합니다.

        Returns
        -------
        (best_match_text, status_message)
        """
        full_lyrics, status = self.searcher.search_lyrics(song_title)
        if status:
            self.last_status = status

        if not full_lyrics:
            return ocr_text, status

        ocr_stripped = ocr_text.strip()

        # ── 전략 1: OCR 결과가 너무 짧으면 매핑하지 않음 ──────────────────
        # 예) "Me", "I", "Oh" 같은 극단적으로 짧은 OCR은 원문 그대로
        if len(ocr_stripped) <= _MIN_OCR_LEN:
            return ocr_text, status

        # ── 전략 2: 후보 가사 중 OCR보다 현저히 짧은 것 제외 ───────────────
        # 예) OCR="It's Me"(6자) → 최소 4자 미만 후보("Me" 등) 제거
        min_len = max(1, int(len(ocr_stripped) * _CANDIDATE_LEN_RATIO))
        filtered = [ln for ln in full_lyrics if len(ln.strip()) >= min_len]

        # 필터링 후 후보가 없으면 전체 가사로 다시 시도
        pool = filtered if filtered else full_lyrics

        match = process.extractOne(
            ocr_stripped, pool, scorer=fuzz.WRatio, score_cutoff=60
        )
        if match:
            return match[0], status

        return ocr_text, status
