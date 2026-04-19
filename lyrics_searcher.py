import re

class LyricsSearcher:
    def __init__(self):
        self.current_song = ""
        self.cached_lyrics = []

    def search_lyrics(self, query):
        """곡 제목으로 가사 리스트 가져오기"""
        # 검색어 정규화 (공백 제거 등)
        clean_query = re.sub(r'[^a-zA-Z0-9가-힣]', '', query)
        
        # 테스트용: '잠시만 안녕' (M.C the MAX) 매칭
        if "잠시만안녕" in clean_query or "MCtheMAX" in clean_query:
            if self.current_song != "잠시만 안녕":
                print(f"🌐 [DB] '잠시만 안녕' 가사 데이터를 로드했습니다.")
                self.current_song = "잠시만 안녕"
                self.cached_lyrics = self._fetch_from_web(query)
            return self.cached_lyrics
        
        return []

    def _fetch_from_web(self, query):
        # 사용자께서 제공해주신 '잠시만 안녕' 전체 가사 리스트
        return [
            "행복을 줄 수 없었어",
            "그런데 사랑을 했어",
            "니곁에 감히 머무른",
            "내 욕심을 용서치마",
            "방황이 많이 남았어",
            "그 끝은 나도 모르는곳",
            "약하게 태어나서 미안해",
            "그래서 널 보내려고 해",
            "언젠가는 돌아갈께",
            "사랑할 자격 갖춘 나 되어",
            "너의 곁으로 돌아갈께",
            "행복을 줄 수 있을 때",
            "아파도 안녕",
            "잠시만 안녕",
            "언제나 위태로운 나",
            "그런 내가 널 사랑을 했어",
            "외로운 고독이 두려워",
            "빨리 못 보내 미안해",
            "사는게 참 힘들었어",
            "널 보며 난 견뎠어",
            "허나 네겐 보여줄 수",
            "없는 내 삶",
            "이별로 널 지키려해",
            "언젠가는 돌아갈께",
            "흔들리지 않는 나 되어",
            "늦지않게 돌아갈께",
            "널 많이 사랑하니까",
            "아파도 안녕",
            "슬퍼도 안녕",
            "언젠가는 돌아갈께",
            "사랑할 자격 갖춘 나 되어",
            "너의 곁으로 돌아갈께",
            "행복을 줄 수 있을 때",
            "아파도 안녕",
            "널 위해 안녕",
            "너와 내가 사랑하면",
            "우리가 정말 사랑한다면",
            "언젠가는 만날꺼야",
            "행복을 줄 수 있을 때",
            "조금만 울자 잠시만 울자",
            "아파도 안녕",
            "널 위해 안녕"
        ]