from rapidfuzz import process, fuzz  # type: ignore

from lyrics.searcher import LyricsSearcher


class LyricMatcher:
    """OCR 결과를 실제 가사와 퍼지 매칭하여 정답 문장을 반환합니다."""

    def __init__(self):
        self.searcher = LyricsSearcher()
        self.last_status: str | None = None

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

        match = process.extractOne(
            ocr_text, full_lyrics, scorer=fuzz.WRatio, score_cutoff=60
        )
        if match:
            return match[0], status
        return ocr_text, status
