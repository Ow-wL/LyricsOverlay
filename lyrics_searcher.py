import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

class LyricsSearcher:
    def __init__(self):
        self.current_song = ""
        self.cached_lyrics = []
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer': 'https://www.melon.com/index.htm'
        }

    def search_lyrics(self, query):
        # 1. 화면 표시용 이름 정리
        display_name = query.replace("- Melon", "").strip()
        
        # 2. 검색용 정제 (괄호 제거 등)
        clean_query = re.sub(r'[\(\[].*?[\)\]]', '', query)
        clean_query = clean_query.replace("- Melon", "").replace("-", " ").strip()
        clean_query = " ".join(clean_query.split())

        if not clean_query: return [], None

        # [핵심] 이미 검색했던 곡(성공 혹은 실패)이라면 더 이상 시도하지 않음
        if self.current_song == clean_query:
            return self.cached_lyrics, None

        # 새로운 곡이 들어오면 일단 현재 곡으로 등록 (실패해도 다시 안 하도록)
        self.current_song = clean_query
        self.cached_lyrics = [] # 가사 초기화

        try:
            encoded_query = quote(clean_query)
            search_url = f"https://www.melon.com/search/total/index.htm?q={encoded_query}"
            
            response = self.session.get(search_url, headers=self.headers, timeout=5)
            if response.status_code != 200:
                return [], f"❌ 접근 실패: {display_name} (HTTP {response.status_code})"

            soup = BeautifulSoup(response.text, 'html.parser')
            song_link = soup.select_one("a[href*='goSongDetail']")
            
            if not song_link:
                return [], f"❌ 검색 결과 없음: {display_name}"

            song_id = re.findall(r'\d+', song_link['href'])[0]
            
            # 가사 상세 페이지 요청
            lyrics_url = f"https://www.melon.com/song/detail.htm?songId={song_id}"
            res = self.session.get(lyrics_url, headers=self.headers, timeout=5)
            l_soup = BeautifulSoup(res.text, 'html.parser')
            
            lyric_div = l_soup.select_one("#d_video_summary")
            if lyric_div:
                text_raw = lyric_div.get_text(separator="\n").strip()
                self.cached_lyrics = [line.strip() for line in text_raw.split('\n') if line.strip()]
                
                line_count = len(self.cached_lyrics)
                return self.cached_lyrics, f"✅ 로드 성공: {display_name} ({line_count}줄)"
            else:
                return [], f"❌ 가사 데이터 없음: {display_name}"
            
        except Exception as e:
            return [], f"⚠️ 에러: {display_name} ({str(e)})"