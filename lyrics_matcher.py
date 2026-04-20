from rapidfuzz import process, fuzz # type: ignore
from lyrics_searcher import LyricsSearcher

class LyricMatcher:
    def __init__(self):
        self.searcher = LyricsSearcher()
        self.last_status = None 

    def get_best_match(self, ocr_text, song_title):
        """OCR 결과와 실제 가사를 대조하여 정답 문장 반환"""
        # 1. 가사와 상태 메시지를 함께 가져옴
        full_lyrics, status = self.searcher.search_lyrics(song_title)
        if status: self.last_status = status # 새로운 로그가 있으면 저장
        
        if not full_lyrics: return ocr_text, status

        # 2. 유사도 매칭 (기존과 동일)
        match = process.extractOne(ocr_text, full_lyrics, scorer=fuzz.WRatio, score_cutoff=60)
        
        if match:
            return match[0], status
        return ocr_text, status