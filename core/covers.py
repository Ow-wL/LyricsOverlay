"""앨범 커버 저장소.

- 가사를 찾을 때 알게 된 멜론 앨범 이미지 주소로 작은 커버(300px)를 받아 데이터 폴더/covers에 저장합니다.
- 커버 정보가 없는 예전 감상 기록은 자동으로 찾지 않습니다. 사용자가 설정에서 '예전 기록 커버 채우기'를
  눌렀을 때만 곡당 검색 1번 + 곡 페이지 1번씩 천천히 찾습니다.
- 받는 곳은 멜론 이미지 서버(https://cdnimg.melon.co.kr/)뿐이고, 응답 크기를 제한하며,
  요청 간격·거절 시 멈춤은 core.melon_http를 따릅니다.
- 설정에서 커버 받기를 끄면(enabled=False) 새로 받지 않고, 이미 받은 커버만 보여 줍니다.
- 화면 쪽은 path_for()로 파일 경로만 묻고, 새 커버가 생기면 take_updated()가 True가 됩니다.
"""

import json
import os
import queue
import re
import threading
import time
from urllib.parse import quote

import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore

from core import melon_http

_COVER_PREFIX = "https://cdnimg.melon.co.kr/"
_RESIZE = "/melon/resize/300/quality/85/optimize"
_MAX_BYTES = 2 * 1024 * 1024
_BACKFILL_GAP_SEC = 4.0          # 예전 기록 채우기: 요청 사이 간격 (곡 하나에 요청 3번, 약 10초)
BACKFILL_MAX_PER_RUN = 20        # 한 번 누를 때 찾는 곡 수 상한 (멜론에 요청이 몰리지 않게)
BACKFILL_COOLDOWN_SEC = 10 * 60  # 한 번 채운 뒤 다음 채우기까지 기다리는 시간
AUTO_BACKFILL_INTERVAL_SEC = 5 * 60  # '자동으로 조금씩 채우기': 이 간격으로 한 곡씩
_MISS_RETRY_SEC = 7 * 24 * 3600  # 못 찾은 곡은 일주일 뒤 다시 시도
_SONG_ID = re.compile(r"^\d{5,12}$")


def _key(title: str, artist: str) -> str:
    return f"{(title or '').strip()}\t{(artist or '').strip()}"


def valid_cover_url(url) -> bool:
    return isinstance(url, str) and url.startswith(_COVER_PREFIX) and ".." not in url and len(url) < 400


class CoverStore:
    def __init__(self, data_dir: str):
        self._lock = threading.Lock()
        self._index: dict[str, dict] = {}
        self._queued: set[str] = set()
        self._jobs: "queue.Queue" = queue.Queue()
        self._updated = False
        self._stop = threading.Event()
        self.enabled = True
        self.backfill_left = 0  # 채우기 작업 중 남은 곡 수 (화면 표시용)
        self._backfill_started = None  # 마지막으로 채우기를 시작한 시각 (time.monotonic)
        self.set_data_dir(data_dir)
        self._thread = threading.Thread(target=self._worker, name="covers", daemon=True)
        self._thread.start()

    # -- 경로·색인 ------------------------------------------------------- #

    def set_data_dir(self, data_dir: str) -> None:
        with self._lock:
            self.dir = os.path.join(data_dir, "covers")
            self._index_path = os.path.join(self.dir, "index.json")
            self._index = self._load_index()
            self._queued.clear()

    def _load_index(self) -> dict:
        try:
            with open(self._index_path, encoding="utf-8") as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, dict)}
        except (OSError, ValueError):
            return {}

    def _save_index(self) -> None:
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self._index_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False)
            os.replace(tmp, self._index_path)
        except OSError as e:
            print(f"[⚠️] 커버 색인 저장 실패: {e}")

    def _file(self, song_id: str) -> str:
        return os.path.join(self.dir, f"{song_id}.jpg")

    def path_for(self, title: str, artist: str, song_id=None) -> str | None:
        """저장된 커버 파일 경로. 없으면 None이고, 예전 기록이면 찾기를 예약합니다."""
        with self._lock:
            sid = song_id if isinstance(song_id, str) and _SONG_ID.match(song_id) else None
            info = self._index.get(_key(title, artist))
            if sid is None and info:
                sid = info.get("song_id")
            if sid and os.path.exists(self._file(sid)):
                return self._file(sid)
        return None

    def song_id_for(self, title: str, artist: str) -> str | None:
        """예전에 커버를 받으며 알아 둔 곡 ID (없으면 None). 가사 검색을 건너뛰는 데 씁니다."""
        with self._lock:
            sid = (self._index.get(_key(title, artist)) or {}).get("song_id")
        return sid if isinstance(sid, str) and _SONG_ID.match(sid) else None

    def take_updated(self) -> bool:
        """마지막 호출 이후 새 커버가 저장됐는지 (화면을 다시 그릴지)."""
        with self._lock:
            updated, self._updated = self._updated, False
        return updated

    # -- 예약 ------------------------------------------------------------- #

    def remember(self, title: str, artist: str, song_id: str, url: str) -> None:
        """가사 검색에서 알게 된 곡 ID·커버 주소를 기록하고 커버를 받습니다."""
        if not self.enabled:
            return
        if not (isinstance(song_id, str) and _SONG_ID.match(song_id) and valid_cover_url(url)):
            return
        key = _key(title, artist)
        with self._lock:
            self._index[key] = {"song_id": song_id, "url": url}
            self._queued.add(key)
        self._jobs.put(("download", key, song_id, url))

    def backfill_wait(self) -> float:
        """다음 채우기를 시작할 수 있을 때까지 남은 초 (바로 할 수 있으면 0)."""
        if self._backfill_started is None:
            return 0.0
        return max(0.0, self._backfill_started + BACKFILL_COOLDOWN_SEC - time.monotonic())

    def backfill(self, entries, limit: int = BACKFILL_MAX_PER_RUN, auto: bool = False) -> tuple[int, int]:
        """예전 감상 기록 중 커버가 없는 곡을 찾기 예약합니다.

        한 번에 `limit`곡까지만, 목록의 앞쪽(최근에 들은 곡)부터 예약합니다. 직전 채우기에서
        `BACKFILL_COOLDOWN_SEC`가 지나지 않았으면 예약하지 않습니다 (`backfill_wait()` 참고).

        auto=True는 '자동으로 조금씩 채우기'가 부를 때입니다. 부르는 쪽이 간격을 지키므로 대기 시간을
        보지도 시작하지도 않고, 다른 채우기가 진행 중이면 아무것도 하지 않습니다.
        Returns (예약한 곡 수, 이번에 예약하지 못하고 남은 곡 수)
        """
        if not self.enabled or (auto and self.backfill_left > 0):
            return 0, 0
        # 대기 중이거나 멜론 요청을 쉬는 중이면 예약하지 않습니다 (세기만 함).
        cooling = melon_http.paused_for() > 0 or (not auto and self.backfill_wait() > 0)
        n = left_over = 0
        seen = set()
        for e in entries:
            title, artist = e.get("title", ""), e.get("artist", "")
            key = _key(title, artist)
            if key in seen:
                continue
            seen.add(key)
            if self.path_for(title, artist, e.get("song_id")) is not None:
                continue
            if cooling or n >= limit:
                left_over += self._backfill_wanted(title, artist)
            elif self._request_backfill(title, artist):
                n += 1
        if n and not auto:
            self._backfill_started = time.monotonic()
        with self._lock:
            self.backfill_left += n
        return n, left_over

    def _backfill_wanted(self, title: str, artist: str) -> bool:
        """채우기 대상인지 (가수를 알고, 이미 예약되지 않았고, 최근에 못 찾은 곡이 아님)."""
        if not title or (artist or "").strip() in ("", "Unknown"):
            return False
        key = _key(title, artist)
        with self._lock:
            info = self._index.get(key)
            if key in self._queued:
                return False
            return not (info and info.get("miss") and time.time() - info["miss"] < _MISS_RETRY_SEC)

    def _request_backfill(self, title: str, artist: str) -> bool:
        if not self._backfill_wanted(title, artist):
            return False
        key = _key(title, artist)
        with self._lock:
            info = self._index.get(key)
            self._queued.add(key)
        if info and info.get("song_id") and valid_cover_url(info.get("url")):
            self._jobs.put(("download", key, info["song_id"], info["url"], True))  # 채우기에서 온 작업
        else:
            self._jobs.put(("resolve", key, title, artist))
        return True

    def cancel_backfill(self) -> None:
        """예약된 작업을 모두 버립니다 (커버 받기를 끄거나, 커버를 지우거나, 멜론이 거절했을 때)."""
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                break
            if job is None:  # 종료 신호는 되돌려 둠
                self._jobs.put(None)
                break
        with self._lock:
            self._queued.clear()
            self.backfill_left = 0
            self._updated = True

    def clear(self) -> int:
        """받아 둔 커버와 색인을 지웁니다. 지운 파일 수."""
        self.cancel_backfill()
        removed = 0
        with self._lock:
            try:
                for name in os.listdir(self.dir):
                    if name.endswith((".jpg", ".json", ".tmp")):
                        os.remove(os.path.join(self.dir, name))
                        removed += 1
            except OSError:
                pass
            self._index = {}
            self._updated = True
        return removed

    def file_count(self) -> int:
        try:
            return sum(1 for n in os.listdir(self.dir) if n.endswith(".jpg"))
        except OSError:
            return 0

    def shutdown(self) -> None:
        self._stop.set()
        self._jobs.put(None)

    # -- 작업 스레드 ------------------------------------------------------ #

    def _worker(self) -> None:
        from lyrics.searcher import (  # 순환 import 방지
            LyricsSearcher, cover_url_from_detail, parse_search_rows, pick_best_row, search_query_for,
        )

        fetcher = LyricsSearcher()  # 요청 세션·크기 제한만 빌려 씁니다 (이 스레드 전용)
        fetcher.shutdown()
        while not self._stop.is_set():
            job = self._jobs.get()
            if job is None:
                return
            # 채우기로 예약한 작업(곡 찾기, 저장된 주소로 바로 받기)은 끝나면 남은 곡 수에서 뺍니다.
            counted = job[0] == "resolve" or (len(job) > 4 and job[4])
            if not self.enabled:
                self._finish(job[1], counted=counted)
                continue
            try:
                if job[0] == "download":
                    key, sid, url = job[1:4]
                    self._download(fetcher, sid, url)
                else:
                    _, key, title, artist = job
                    time.sleep(_BACKFILL_GAP_SEC)
                    rows = parse_search_rows(fetcher._get_text(
                        "https://www.melon.com/search/song/index.htm?q=" + quote(search_query_for(title, artist))))
                    best, _score = pick_best_row(rows, title, artist)
                    if best is None:
                        self._mark_miss(key)
                        self._finish(key, counted=True)
                        continue
                    sid = best[0]
                    time.sleep(_BACKFILL_GAP_SEC)
                    soup = BeautifulSoup(fetcher._get_text(
                        f"https://www.melon.com/song/detail.htm?songId={sid}"), "html.parser")
                    url = cover_url_from_detail(soup)
                    if not url:
                        self._mark_miss(key)
                        self._finish(key, counted=True)
                        continue
                    with self._lock:
                        self._index[key] = {"song_id": sid, "url": url}
                    self._download(fetcher, sid, url)
            except melon_http.MelonPaused:
                # 멜론이 거절해 쉬는 중이면 남은 채우기 작업을 접습니다 (나중에 다시 누르면 이어서)
                self.cancel_backfill()
                continue
            except Exception as e:
                print(f"[⚠️] 앨범 커버를 가져오지 못했습니다: {e}")
                self._mark_miss(job[1])
            self._finish(job[1], counted=counted)

    def _finish(self, key: str, counted: bool) -> None:
        """작업 하나가 끝나면 '예약됨' 표시를 지웁니다 (못 찾은 곡의 7일 뒤 재시도가 막히지 않게)."""
        with self._lock:
            self._queued.discard(key)
            if counted and self.backfill_left > 0:
                self.backfill_left -= 1
                self._updated = True

    def _mark_miss(self, key: str) -> None:
        with self._lock:
            self._index[key] = {"miss": time.time()}
            self._save_index()

    def _download(self, fetcher, sid: str, url: str) -> None:
        path = self._file(sid)
        if not os.path.exists(path):
            melon_http.wait_turn()
            try:
                res = fetcher.session.get(url + _RESIZE, headers=fetcher.headers, timeout=(5, 10), stream=True)
            except (requests.ConnectionError, requests.Timeout):
                melon_http.report_error()  # 응답을 못 받은 실패도 연속 실패로 셈
                raise
            melon_http.report_status(res.status_code)
            res.raise_for_status()
            if not res.headers.get("content-type", "").startswith("image/"):
                raise ValueError("이미지가 아닌 응답")
            data = b""
            for chunk in res.iter_content(64 * 1024):
                data += chunk
                if len(data) > _MAX_BYTES:
                    raise ValueError("이미지가 너무 큽니다")
            os.makedirs(self.dir, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        with self._lock:
            self._updated = True
            self._save_index()


# 화면 쪽에서 쓰는 전역 저장소 (main.py가 만듭니다. 없으면 커버 없이 동작)
store: CoverStore | None = None


def path_for(title: str, artist: str, song_id=None) -> str | None:
    return store.path_for(title, artist, song_id) if store is not None else None
