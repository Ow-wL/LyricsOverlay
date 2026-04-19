import requests
from bs4 import BeautifulSoup
import re

class LyricsSearcher:
    def __init__(self):
        self.current_song = ""
        self.cached_lyrics = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        }

    def search_lyrics(self, query):
        # 1. 검색어 정제 (핵심!)
        # 괄호 안의 내용 제거: "12:45 (Stripped) - Etham" -> "12:45 - Etham"
        temp_query = re.sub(r'\(.*?\)', '', query)
        # " - Melon" 꼬리표 제거 및 불필요한 특수문자 정리
        clean_query = temp_query.replace("- Melon", "").replace("-", " ").strip()
        # 중복 공백 제거
        clean_query = " ".join(clean_query.split())

        if self.current_song == clean_query:
            return self.cached_lyrics, None

        try:
            # 2. 멜론 검색 시도
            search_url = f"https://www.melon.com/search/song/index.htm?q={clean_query}"
            response = requests.get(search_url, headers=self.headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 곡 상세 페이지 링크 찾기
            song_link = soup.select_one("a.btn.btn_icon_detail")
            
            if not song_link:
                # [재시도 로직] 만약 실패하면 더 단순하게 검색 (가수 빼고 제목만)
                simple_query = clean_query.split()[0] # 첫 단어만
                return [], f"❌ 검색 실패: '{clean_query}' (단순 검색 권장)"

            song_id = re.findall(r'\d+', song_link['href'])[0]
            lyrics_list = self._fetch_melon_lyrics(song_id)
            
            if lyrics_list:
                self.current_song = clean_query
                self.cached_lyrics = lyrics_list
                return lyrics_list, f"✅ 로드 완료: {clean_query} ({len(lyrics_list)}줄)"
            else:
                return [], "⚠️ 가사 정보가 없는 곡입니다."
                
        except Exception as e:
            return [], f"⚠️ 에러: {str(e)}"

    def _fetch_melon_lyrics(self, song_id):
        url = f"https://www.melon.com/song/detail.htm?songId={song_id}"
        response = requests.get(url, headers=self.headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 멜론은 가사가 없으면 해당 div가 아예 없거나 비어있음
        lyric_div = soup.select_one("#d_video_summary")
        if not lyric_div:
            return []

        # 줄바꿈 처리
        for br in lyric_div.find_all("br"):
            br.replace_with("\n")
        
        raw_lyrics = lyric_div.get_text()
        return [line.strip() for line in raw_lyrics.split('\n') if line.strip()]