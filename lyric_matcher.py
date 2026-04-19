from rapidfuzz import process, fuzz
from lyrics_searcher import LyricsSearcher

class LyricMatcher:
    def __init__(self):
        self.searcher = LyricsSearcher()

    def get_best_match(self, ocr_text, song_title):
        """OCR 결과와 실제 가사를 대조하여 정답 문장 반환"""
        # 1. 현재 노래 가사 가져오기
        full_lyrics = self.searcher.search_lyrics(song_title)
        
        if not full_lyrics or not ocr_text:
            return ocr_text

        # 2. 유사도 매칭 실행 (임계값 60% 설정)
        # ocr_text와 가장 비슷한 문장을 full_lyrics에서 찾음
        match_result = process.extractOne(
            ocr_text, 
            full_lyrics, 
            scorer=fuzz.WRatio
        )

        if match_result:
            best_text, score, _ = match_result
            if score > 60: # 60% 이상 비슷할 때만 교체
                return best_text
        
        return ocr_text