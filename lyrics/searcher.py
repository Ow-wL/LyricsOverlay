import requests  # type: ignore

from core import melon_http
from bs4 import BeautifulSoup  # type: ignore
from rapidfuzz import fuzz  # type: ignore
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable
from urllib.parse import quote

# 네트워크 오류 등 일시적인 실패 후 다시 시도하기까지 기다리는 시간
_RETRY_AFTER_SEC = 30.0

# 멜론 페이지는 보통 수백 KB입니다. 이보다 크거나 오래 걸리면 비정상 응답으로 보고 끊습니다.
_MAX_RESPONSE_BYTES = 3 * 1024 * 1024
_MAX_RESPONSE_SEC = 15.0

# 이번 실행에서 가사를 받은 곡을 이만큼 기억합니다 (메모리에만, 파일로 저장하지 않음).
# 같은 곡을 다시 들을 때 멜론에 다시 묻지 않기 위한 것입니다.
_CACHE_SONGS = 50

_SONG_ID = re.compile(r"^\d{5,12}$")

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


def search_query_for(want_title: str, want_artist: str) -> str:
    """멜론 검색어: 괄호 속 부가 정보와 기호를 뺀 제목 + 가수."""
    clean_title = re.sub(r"[\(\[].*?[\)\]]", "", want_title).strip()
    clean_title = " ".join(re.sub(r"[^a-zA-Z0-9가-힣\s]", " ", clean_title).split())
    return f"{clean_title} {want_artist}".strip()


def parse_search_rows(html: str) -> list[tuple[str, str, str]]:
    """멜론 곡 검색 결과 페이지 → [(song_id, 제목, 가수)] (최대 10개)."""
    soup = BeautifulSoup(html, "html.parser")
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
    return rows


_COVER_PREFIX = "https://cdnimg.melon.co.kr/"


def cover_url_from_detail(soup) -> str | None:
    """곡 상세 페이지의 앨범 이미지 주소 (멜론 이미지 서버 주소만 받습니다)."""
    tag = soup.select_one('meta[property="og:image"]')
    url = (tag.get("content") or "").strip() if tag else ""
    if not url.startswith(_COVER_PREFIX) or not url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
        return None
    return url


def melon_song_url(title: str, artist: str, song_id=None) -> str:
    """감상 기록 한 곡을 멜론에서 여는 주소. 곡 ID를 알면 곡 상세, 모르면 멜론 검색."""
    if isinstance(song_id, str) and song_id.isdigit() and 5 <= len(song_id) <= 12:
        return f"https://www.melon.com/song/detail.htm?songId={song_id}"
    query = " ".join(f"{title or ''} {artist if artist and artist != 'Unknown' else ''}".split())
    return f"https://www.melon.com/search/total/index.htm?q={quote(query)}"


class LyricsSearcher:
    """멜론에서 가사를 검색하고 캐싱하는 클래스."""

    def __init__(self):
        self.current_song = ""
        self.cached_lyrics: list[str] = []
        self.session = requests.Session()
        # 앱 이름을 밝히는 헤더 (브라우저인 척하지 않음). 요청 간격·거절 시 멈춤은 core.melon_http가 맡습니다.
        self.headers = dict(melon_http.HEADERS)
        # 설정 '멜론에서 가사 원문 가져오기'. 끄면 멜론에 요청하지 않고 OCR 결과만 씁니다.
        self.enabled = True
        # requests.Session은 이 작업 스레드 하나에서만 씁니다.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lyrics")
        self._future: Future | None = None
        self._retry_at: float | None = None
        # 가사를 찾은 곡의 멜론 곡 ID ('제목 - 가수' → ID). 감상 기록에서 멜론 링크로 씁니다.
        self.song_ids: dict[str, str] = {}
        self.song_covers: dict[str, str] = {}  # '제목 - 가수' → 앨범 이미지 주소
        # 예전에 알아 둔 곡 ID를 찾는 함수 ('제목 - 가수' → 곡 ID 또는 None). 알면 검색을 건너뛰고 곡 페이지만 받습니다.
        # 검색 작업 스레드에서 부르므로, 읽기만 하는 가벼운 함수여야 합니다.
        self.id_lookup: Callable[[str], str | None] | None = None
        self._cache: "OrderedDict[str, list[str]]" = OrderedDict()  # 이번 실행에서 받은 가사 (메모리에만)
        self._cache_lock = threading.Lock()

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
        if not self.enabled:
            # 지금 곡을 '아직 찾지 않은 곡'으로 둡니다. 그래야 같은 곡을 듣는 중에 다시 켜도 바로 찾습니다.
            self.current_song = ""
            self.cached_lyrics = []
            if self._future is not None:
                self._future.cancel()
                self._future = None
            return [], None

        if display_name != self.current_song:
            # 이전 곡 검색이 아직 대기 중이면 취소하고, 실행 중이면 결과만 버립니다.
            if self._future is not None:
                self._future.cancel()
            self.current_song = display_name
            self._retry_at = None
            remembered = self._cached(display_name)
            if remembered is not None:
                # 이번 실행에서 이미 받은 곡(가사가 없다는 결과 포함): 멜론에 다시 묻지 않습니다.
                self._future = None
                self.cached_lyrics = remembered
                return self.cached_lyrics, self._replay_status(display_name, remembered)
            self.cached_lyrics = []
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

    def song_id_for(self, query: str) -> str | None:
        return self.song_ids.get(query.replace("- Melon", "").strip())

    def cover_for(self, query: str) -> str | None:
        return self.song_covers.get(query.replace("- Melon", "").strip())

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _cached(self, display_name: str) -> list[str] | None:
        with self._cache_lock:
            lines = self._cache.get(display_name)
            if lines is not None:
                self._cache.move_to_end(display_name)
            return lines

    def _remember(self, display_name: str, lines: list[str]) -> None:
        with self._cache_lock:
            self._cache[display_name] = lines
            self._cache.move_to_end(display_name)
            while len(self._cache) > _CACHE_SONGS:
                self._cache.popitem(last=False)

    def _known_id(self, display_name: str) -> str | None:
        sid = self.song_ids.get(display_name)
        if sid is None and self.id_lookup is not None:
            try:
                sid = self.id_lookup(display_name)
            except Exception:
                sid = None
        return sid if isinstance(sid, str) and _SONG_ID.match(sid) else None

    def _get_text(self, url: str) -> str:
        """페이지를 받아 문자열로. 너무 크거나 오래 걸리는 응답은 중간에 끊습니다.

        requests의 timeout은 '응답 전체' 상한이 아니라 연결·읽기 대기 시간이라,
        조금씩 계속 오는 응답이나 비정상적으로 큰 응답이 검색 스레드를 오래 붙잡을 수 있습니다.
        """
        melon_http.wait_turn()  # 최소 간격, 쉬는 중이면 MelonPaused
        start = time.monotonic()
        try:
            with self.session.get(url, headers=self.headers, timeout=(5, 5), stream=True) as res:
                melon_http.report_status(res.status_code)  # 거절이면 쉬고, 다른 오류 응답은 실패로 셈
                res.raise_for_status()  # 차단·서버 오류는 재시도 대상으로
                chunks, size = [], 0
                for chunk in res.iter_content(64 * 1024):
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES:
                        raise ValueError(f"응답이 너무 큽니다 ({_MAX_RESPONSE_BYTES // 1024 // 1024}MB 초과)")
                    if time.monotonic() - start > _MAX_RESPONSE_SEC:
                        raise TimeoutError(f"응답이 {_MAX_RESPONSE_SEC:.0f}초 안에 끝나지 않았습니다")
                    chunks.append(chunk)
                encoding = res.encoding or res.apparent_encoding or "utf-8"
        except requests.HTTPError:
            raise  # 응답 코드는 위의 report_status가 이미 셌습니다
        except Exception:
            melon_http.report_error()  # 연결 실패, 시간 초과, 비정상적으로 큰 응답도 실패로 셉니다
            raise
        return b"".join(chunks).decode(encoding, errors="replace")

    def _load_detail(self, song_id: str) -> dict:
        """곡 페이지 한 번으로 가사·커버 주소·페이지에 적힌 제목과 가수를 받습니다 (아직 아무 데도 기록하지 않음)."""
        soup = BeautifulSoup(self._get_text(f"https://www.melon.com/song/detail.htm?songId={song_id}"), "html.parser")
        lines: list[str] = []
        lyric_div = soup.select_one("#d_video_summary") or soup.select_one(".lyric_area")
        if lyric_div:
            text_raw = lyric_div.get_text(separator="\n").strip()
            found = [line.strip() for line in text_raw.split("\n") if line.strip()]
            if len(found) > 2:
                lines = found
        og_title = soup.select_one('meta[property="og:title"]')  # '제목 - 가수'
        title, artist = split_title((og_title.get("content") or "").strip()) if og_title else ("", "")
        return {"lines": lines, "cover": cover_url_from_detail(soup), "title": title, "artist": artist}

    @staticmethod
    def _page_matches(page: dict, want_title: str, want_artist: str) -> bool:
        """받은 곡 페이지가 찾는 곡이 맞는지. 페이지에서 제목을 읽지 못하면 확인할 수 없으므로 False."""
        if not page.get("title"):
            return False
        return score_row(want_title, want_artist, page["title"], page.get("artist", "")) >= _MIN_ROW_SCORE

    def _finish_song(self, display_name: str, song_id: str, page: dict, note: str = "") -> tuple[list[str], str, bool]:
        """확인된 곡 페이지의 결과를 기록하고 돌려줍니다. 가사가 없다는 결과도 기억해 다시 묻지 않습니다."""
        # 커버 주소를 먼저, 곡 ID를 나중에 적습니다 (곡 ID가 보이면 커버 주소도 이미 있도록).
        if page.get("cover"):
            if len(self.song_covers) > 500:
                self.song_covers.clear()
            self.song_covers[display_name] = page["cover"]
        if len(self.song_ids) > 500:
            self.song_ids.clear()
        self.song_ids[display_name] = str(song_id)
        lines = page.get("lines") or []
        self._remember(display_name, lines)
        if lines:
            extra = f", {note}" if note else ""
            return lines, f"✅ 로드 성공: {display_name} ({len(lines)}줄{extra})", False
        return [], f"❌ 가사 데이터 없음 (ID:{song_id}): {display_name}", False

    @staticmethod
    def _replay_status(display_name: str, lines: list[str]) -> str:
        if lines:
            return f"✅ 다시 듣는 곡 (요청 없음): {display_name} ({len(lines)}줄)"
        return f"❌ 가사 없는 곡 (요청 없음): {display_name}"

    def _fetch(self, query: str, display_name: str) -> tuple[list[str], str, bool]:
        """(백그라운드 스레드) 멜론에서 가사를 가져옵니다.

        Returns (lines, status_message, retryable)
        """
        # 이 작업이 차례를 기다리는 사이에 같은 곡을 이미 받았을 수 있습니다 (A → B → A로 빨리 넘긴 경우).
        cached = self._cached(display_name)
        if cached is not None:
            return cached, self._replay_status(display_name, cached), False

        want_title, want_artist = split_title(query)
        search_query = search_query_for(want_title, want_artist)

        try:
            # 1) 예전에 알아 둔 곡 ID가 있으면 검색을 건너뛰고 곡 페이지만 받습니다 (요청 2번 → 1번).
            #    받은 페이지의 제목·가수가 찾는 곡과 맞을 때만 씁니다 (잘못 기록된 ID로 다른 곡 가사를 쓰지 않도록).
            known = self._known_id(display_name)
            page, known_failed = None, False
            if known:
                try:
                    page = self._load_detail(known)
                except melon_http.MelonPaused:
                    raise
                except Exception as e:
                    known_failed = True
                    print(f"[DEBUG] 알고 있던 곡 ID({known})로 받지 못해 검색합니다: {e}")
                if page is not None and self._page_matches(page, want_title, want_artist):
                    return self._finish_song(display_name, known, page, "검색 생략")
                if page is not None:
                    print(f"[DEBUG] 알고 있던 곡 ID({known})의 페이지가 찾는 곡과 달라 검색합니다")

            # 2) 멜론에서 곡을 검색합니다.
            search_url = f"https://www.melon.com/search/song/index.htm?q={quote(search_query)}"
            rows = parse_search_rows(self._get_text(search_url))
            if not rows:
                print(f"[DEBUG] 검색 결과 없음: {search_query}")
                self._remember(display_name, [])
                return [], f"❌ 검색 결과 없음: {display_name}", False

            best, score = pick_best_row(rows, want_title, want_artist)
            if best is None:
                # 첫 결과를 그냥 쓰면 다른 곡의 가사로 '보정'해 버리므로 OCR 원문을 그대로 씁니다.
                self._remember(display_name, [])
                return [], f"❌ 같은 곡을 찾지 못함 (가장 비슷한 결과 {score:.0f}점): {display_name}", False
            song_id = str(best[0])
            print(f"[DEBUG] 찾은 곡 ID: {song_id} ({best[1]} - {best[2]}, {score:.0f}점)")

            if not song_id or len(song_id) < 5:
                return [], f"❌ 올바른 곡 ID를 찾지 못함: {display_name}", False
            if song_id == known:
                if known_failed or page is None:
                    # 방금 그 곡 페이지를 받지 못했습니다. 같은 요청을 바로 되풀이하지 않고 잠시 뒤 다시 시도합니다.
                    return [], f"⚠️ 에러: {display_name} (곡 페이지를 받지 못함)", True
                # 검색도 같은 곡이라고 확인했습니다. 이미 받은 페이지를 그대로 씁니다 (다시 받지 않음).
                return self._finish_song(display_name, song_id, page)

            return self._finish_song(display_name, song_id, self._load_detail(song_id))

        except melon_http.MelonPaused as e:
            return [], f"⏸ {e}: {display_name}", True
        except Exception as e:
            return [], f"⚠️ 에러: {display_name} ({e})", True
