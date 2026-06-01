import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import re
from urllib.parse import quote


class LyricsSearcher:
    """멜론에서 가사를 검색하고 캐싱하는 클래스."""

    def __init__(self):
        self.current_song = ""
        self.cached_lyrics: list[str] = []
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.melon.com/index.htm",
        }

    def search_lyrics(self, query: str) -> tuple[list[str], str | None]:
        """곡 제목 + 가수 쿼리로 멜론에서 가사를 가져옵니다.

        Returns
        -------
        (lyrics_lines, status_message)
        """
        # 표시용 이름 정리
        display_name = query.replace("- Melon", "").strip()

        parts = query.split(" - ")
        if len(parts) < 2:
            return [], None

        # 괄호 제거 및 검색어 조합
        clean_title = re.sub(r"[\(\[].*?[\)\]]", "", parts[0]).strip()
        clean_title_search = " ".join(
            re.sub(r"[^a-zA-Z0-9가-힣\s]", " ", clean_title).split()
        )
        search_query = f"{clean_title_search} {parts[1].strip()}"

        if self.current_song == display_name:
            return self.cached_lyrics, None

        # 한 번 시도한 곡은 실패해도 다시 안 함
        self.current_song = display_name
        self.cached_lyrics = []

        try:
            encoded_query = quote(search_query)
            search_url = (
                f"https://www.melon.com/search/song/index.htm?q={encoded_query}"
            )
            res = self.session.get(search_url, headers=self.headers, timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")

            song_id = None
            search_results = soup.select("div.tb_list table tbody tr")
            if not search_results:
                return [], f"❌ 검색 결과 없음: {display_name}"

            first_row = search_results[0]
            links = str(first_row.select("a[href*='goSongDetail']"))
            id_match = re.search(r"goSongDetail\(['\"](\d+)['\"]\]", links)

            if id_match:
                song_id = id_match.group(1)
            else:
                chk = first_row.select_one("input[name='check_song']")
                if chk:
                    song_id = chk.get("value")

            if not song_id or len(song_id) < 5:
                return [], f"❌ 올바른 곡 ID를 찾지 못함: {display_name}"

            lyrics_url = (
                f"https://www.melon.com/song/detail.htm?songId={song_id}"
            )
            res = self.session.get(lyrics_url, headers=self.headers, timeout=5)
            l_soup = BeautifulSoup(res.text, "html.parser")

            lyric_div = l_soup.select_one("#d_video_summary") or l_soup.select_one(
                ".lyric_area"
            )
            if lyric_div:
                text_raw = lyric_div.get_text(separator="\n").strip()
                lines = [line.strip() for line in text_raw.split("\n") if line.strip()]
                if len(lines) > 2:
                    self.cached_lyrics = lines
                    return self.cached_lyrics, f"✅ 로드 성공: {display_name} ({len(lines)}줄)"

            return [], f"❌ 가사 데이터 없음 (ID:{song_id}): {display_name}"

        except Exception as e:
            return [], f"⚠️ 에러: {display_name} ({e})"
