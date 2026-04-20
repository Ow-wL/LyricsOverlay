import requests # type: ignore
from bs4 import BeautifulSoup # type: ignore
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
        # 1. 표시용 및 검색용 이름 정리
        display_name = query.replace("- Melon", "").strip()
        
        parts = query.split(" - ")
        if len(parts) < 2: return [], None
        
        # 괄호 제거 및 검색어 조합 (12:45 Etham)
        clean_title = re.sub(r'[\(\[].*?[\)\]]', '', parts[0]).strip()
        # 특수문자를 제거하되 공백으로 치환 (12:45 -> 12 45)
        clean_title_search = " ".join(re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', clean_title).split())
        search_query = f"{clean_title_search} {parts[1].strip()}"

        if self.current_song == display_name:
            return self.cached_lyrics, None

        # 한 번 시도한 곡은 실패해도 다시 안 함
        self.current_song = display_name
        self.cached_lyrics = [] 

        try:
            encoded_query = quote(search_query)
            # 곡 검색 페이지 활용
            search_url = f"https://www.melon.com/search/song/index.htm?q={encoded_query}"
            
            res = self.session.get(search_url, headers=self.headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 2. ID 추출 (함수 호출 패턴을 정확히 타겟팅)
            song_id = None
            
            # 검색 결과 테이블 내의 링크들만 탐색
            search_results = soup.select("div.tb_list table tbody tr")
            if not search_results:
                return [], f"❌ 검색 결과 없음: {display_name}"

            # 첫 번째 결과 행에서 ID 추출
            first_row = search_results[0]
            # goSongDetail('31509376') 같은 패턴에서 숫자만 추출
            links = str(first_row.select("a[href*='goSongDetail']"))
            # [수정된 정규식] '숫자' 또는 "숫자" 형태만 8자리 내외로 타겟팅
            id_match = re.search(r"goSongDetail\(['\"](\d+)['\"]", links)
            
            if id_match:
                song_id = id_match.group(1)
            else:
                # 체크박스 value에서 가져오기 (가장 확실함)
                chk = first_row.select_one("input[name='check_song']")
                if chk: song_id = chk.get('value')

            if not song_id or len(song_id) < 5: # ID가 너무 짧으면(예: 12) 가짜임
                return [], f"❌ 올바른 곡 ID를 찾지 못함: {display_name}"

            # 3. 가사 상세 페이지 접속
            lyrics_url = f"https://www.melon.com/song/detail.htm?songId={song_id}"
            res = self.session.get(lyrics_url, headers=self.headers, timeout=5)
            l_soup = BeautifulSoup(res.text, 'html.parser')
            
            lyric_div = l_soup.select_one("#d_video_summary") or l_soup.select_one(".lyric_area")

            if lyric_div:
                text_raw = lyric_div.get_text(separator="\n").strip()
                lines = [line.strip() for line in text_raw.split('\n') if line.strip()]
                
                if len(lines) > 2:
                    self.cached_lyrics = lines
                    return self.cached_lyrics, f"✅ 로드 성공: {display_name} ({len(lines)}줄)"
            
            return [], f"❌ 가사 데이터 없음 (ID:{song_id}): {display_name}"
            
        except Exception as e:
            return [], f"⚠️ 에러: {display_name} ({str(e)})"