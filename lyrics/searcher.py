import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from urllib.parse import quote

# 네트워크 오류 등 일시적인 실패 후 다시 시도하기까지 기다리는 시간
_RETRY_AFTER_SEC = 30.0


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
        # requests.Session은 이 작업 스레드 하나에서만 씁니다.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lyrics")
        self._future: Future | None = None
        self._retry_at: float | None = None

    def search_lyrics(self, query: str) -> tuple[list[str], str | None]:
        """곡 제목 + 가수 쿼리에 해당하는 가사를 돌려줍니다 (UI를 막지 않음).

        새 곡이면 백그라운드 스레드에서 멜론 검색을 시작하고 빈 목록을 돌려줍니다.
        검색이 끝난 뒤의 호출부터 가사가 반환됩니다.

        Returns
        -------
        (lyrics_lines, status_message)
        """
        display_name = query.replace("- Melon", "").strip()
        if len(query.split(" - ")) < 2:
            return [], None

        if display_name != self.current_song:
            # 이전 곡 검색이 아직 대기 중이면 취소하고, 실행 중이면 결과만 버립니다.
            if self._future is not None:
                self._future.cancel()
            self.current_song = display_name
            self.cached_lyrics = []
            self._retry_at = None
            self._future = self._executor.submit(self._fetch, query, display_name)
            return [], f"🔎 가사 검색 중: {display_name}"

        if self._future is not None and self._future.done():
            future, self._future = self._future, None
            try:
                lines, status, retryable = future.result()
            except Exception as e:
                lines, status, retryable = [], f"⚠️ 에러: {display_name} ({e})", True
            self.cached_lyrics = lines
            if retryable:
                self._retry_at = time.monotonic() + _RETRY_AFTER_SEC
            return self.cached_lyrics, status

        if (
            self._future is None
            and self._retry_at is not None
            and time.monotonic() >= self._retry_at
        ):
            self._retry_at = None
            self._future = self._executor.submit(self._fetch, query, display_name)
            return [], f"🔁 가사 재검색: {display_name}"

        return self.cached_lyrics, None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _fetch(self, query: str, display_name: str) -> tuple[list[str], str, bool]:
        """(백그라운드 스레드) 멜론에서 가사를 가져옵니다.

        Returns (lines, status_message, retryable)
        """
        parts = query.split(" - ")

        # 괄호 제거 및 검색어 조합
        clean_title = re.sub(r"[\(\[].*?[\)\]]", "", parts[0]).strip()
        clean_title_search = " ".join(
            re.sub(r"[^a-zA-Z0-9가-힣\s]", " ", clean_title).split()
        )
        search_query = f"{clean_title_search} {parts[1].strip()}"

        try:
            encoded_query = quote(search_query)
            search_url = (
                f"https://www.melon.com/search/song/index.htm?q={encoded_query}"
            )
            res = self.session.get(search_url, headers=self.headers, timeout=5)
            res.raise_for_status()  # 차단·서버 오류는 재시도 대상으로
            soup = BeautifulSoup(res.text, "html.parser")

            song_id = None
            search_results = soup.select("div.tb_list table tbody tr")
            if not search_results:
                print(f"[DEBUG] 검색 결과 없음: {search_query}")
                return [], f"❌ 검색 결과 없음: {display_name}", False

            first_row = search_results[0]
            links = str(first_row.select("a[href*='goSongDetail']"))
            id_match = re.search(r"goSongDetail\(['\"](\d+)['\"]", links)

            if id_match:
                song_id = id_match.group(1)
            else:
                chk = first_row.select_one("input[name='check_song']")
                if chk:
                    song_id = chk.get("value")
                    
            print(f"[DEBUG] 찾은 곡 ID: {song_id}")

            if not song_id or len(str(song_id)) < 5:
                return [], f"❌ 올바른 곡 ID를 찾지 못함: {display_name}", False

            lyrics_url = (
                f"https://www.melon.com/song/detail.htm?songId={song_id}"
            )
            res = self.session.get(lyrics_url, headers=self.headers, timeout=5)
            res.raise_for_status()
            l_soup = BeautifulSoup(res.text, "html.parser")

            lyric_div = l_soup.select_one("#d_video_summary") or l_soup.select_one(
                ".lyric_area"
            )
            if lyric_div:
                text_raw = lyric_div.get_text(separator="\n").strip()
                lines = [line.strip() for line in text_raw.split("\n") if line.strip()]
                if len(lines) > 2:
                    return lines, f"✅ 로드 성공: {display_name} ({len(lines)}줄)", False

            return [], f"❌ 가사 데이터 없음 (ID:{song_id}): {display_name}", False

        except Exception as e:
            return [], f"⚠️ 에러: {display_name} ({e})", True
