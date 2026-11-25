import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from rapidfuzz import fuzz  # type: ignore
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from urllib.parse import quote

# 네트워크 오류 등 일시적인 실패 후 다시 시도하기까지 기다리는 시간
_RETRY_AFTER_SEC = 30.0

# 검색 결과 중 이 점수(0~100) 이상으로 제목·가수가 맞는 곡만 씁니다. 엉뚱한 곡의 가사로 보정하지 않도록.
_MIN_ROW_SCORE = 70


def _norm(text: str) -> str:
    """비교용: 괄호 속 부가 정보(feat., Live 등)와 기호를 빼고 소문자로."""
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text or "")
    text = re.sub(r"[^0-9a-zA-Z가-힣ㄱ-ㅎㅏ-ㅣぁ-んァ-ン一-龥]+", " ", text)
    return " ".join(text.lower().split())


def split_title(query: str) -> tuple[str, str]:
    """'제목 - 가수' → (제목, 가수). 제목에 ' - '가 들어 있어도 마지막 것을 기준으로 나눕니다."""
    title, _, artist = query.rpartition(" - ")
    return title.strip(), artist.strip()


def score_row(want_title: str, want_artist: str, row_title: str, row_artist: str) -> float:
    """검색 결과 한 줄이 찾는 곡과 얼마나 맞는지 (0~100)."""
    t = fuzz.ratio(_norm(want_title), _norm(row_title))
    a = fuzz.token_set_ratio(_norm(want_artist), _norm(row_artist)) if want_artist else 100
    score = t * 0.65 + a * 0.35
    # 라이브·MR 등 다른 버전은 원래 제목에 그 말이 없으면 조금 낮춥니다.
    for tag in ("live", "inst", "mr", "remix", "ver"):
        if tag in _norm(row_title).split() and tag not in _norm(want_title).split():
            score -= 8
    return score


def pick_best_row(rows: list[tuple[str, str, str]], want_title: str, want_artist: str):
    """[(song_id, 제목, 가수)] 중 가장 잘 맞는 줄과 점수. 맞는 게 없으면 (None, 점수)."""
    best, best_score = None, 0.0
    for row in rows:
        sc = score_row(want_title, want_artist, row[1], row[2])
        if sc > best_score:
            best, best_score = row, sc
    if best is None or best_score < _MIN_ROW_SCORE:
        return None, best_score
    return best, best_score


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
        if " - " not in display_name:
            return [], None

        if display_name != self.current_song:
            # 이전 곡 검색이 아직 대기 중이면 취소하고, 실행 중이면 결과만 버립니다.
            if self._future is not None:
                self._future.cancel()
            self.current_song = display_name
            self.cached_lyrics = []
            self._retry_at = None
            self._future = self._executor.submit(self._fetch, display_name, display_name)
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
            self._future = self._executor.submit(self._fetch, display_name, display_name)
            return [], f"🔁 가사 재검색: {display_name}"

        return self.cached_lyrics, None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _fetch(self, query: str, display_name: str) -> tuple[list[str], str, bool]:
        """(백그라운드 스레드) 멜론에서 가사를 가져옵니다.

        Returns (lines, status_message, retryable)
        """
        want_title, want_artist = split_title(query)

        # 괄호 제거 및 검색어 조합
        clean_title = re.sub(r"[\(\[].*?[\)\]]", "", want_title).strip()
        clean_title_search = " ".join(
            re.sub(r"[^a-zA-Z0-9가-힣\s]", " ", clean_title).split()
        )
        search_query = f"{clean_title_search} {want_artist}"

        try:
            encoded_query = quote(search_query)
            search_url = (
                f"https://www.melon.com/search/song/index.htm?q={encoded_query}"
            )
            res = self.session.get(search_url, headers=self.headers, timeout=5)
            res.raise_for_status()  # 차단·서버 오류는 재시도 대상으로
            soup = BeautifulSoup(res.text, "html.parser")

            rows = []
            for tr in soup.select("div.tb_list table tbody tr")[:10]:
                title_a = tr.select_one("a.fc_gray")
                artist_a = tr.select_one("#artistName a.fc_mgray") or tr.select_one("a.fc_mgray")
                id_match = re.search(r"goSongDetail\(['\"]?(\d+)", str(tr))
                chk = tr.select_one("input[name='input_check'], input[name='check_song']")
                song_id = id_match.group(1) if id_match else (chk.get("value") if chk else None)
                if title_a and song_id:
                    rows.append((song_id, title_a.get_text(" ", strip=True),
                                 artist_a.get_text(" ", strip=True) if artist_a else ""))
            if not rows:
                print(f"[DEBUG] 검색 결과 없음: {search_query}")
                return [], f"❌ 검색 결과 없음: {display_name}", False

            best, score = pick_best_row(rows, want_title, want_artist)
            if best is None:
                # 첫 결과를 그냥 쓰면 다른 곡의 가사로 '보정'해 버리므로 OCR 원문을 그대로 씁니다.
                return [], f"❌ 같은 곡을 찾지 못함 (가장 비슷한 결과 {score:.0f}점): {display_name}", False
            song_id = best[0]
            print(f"[DEBUG] 찾은 곡 ID: {song_id} ({best[1]} - {best[2]}, {score:.0f}점)")

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
