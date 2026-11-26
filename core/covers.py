"""앨범 커버 저장소.

- 가사를 찾을 때 알게 된 멜론 앨범 이미지 주소로 작은 커버(300px)를 받아 데이터 폴더/covers에 저장합니다.
- 커버 정보가 없는 예전 감상 기록은 화면에 보일 때 하나씩 천천히(곡당 검색 1번 + 곡 페이지 1번) 찾아 채웁니다.
- 받는 곳은 멜론 이미지 서버(https://cdnimg.melon.co.kr/)뿐이고, 응답 크기도 제한합니다.
- 화면 쪽은 path_for()로 파일 경로만 묻고, 새 커버가 생기면 take_updated()가 True가 됩니다.
"""

import json
import os
import queue
import re
import threading
import time
from urllib.parse import quote

from bs4 import BeautifulSoup  # type: ignore

_COVER_PREFIX = "https://cdnimg.melon.co.kr/"
_RESIZE = "/melon/resize/300/quality/85/optimize"
_MAX_BYTES = 2 * 1024 * 1024
_BACKFILL_GAP_SEC = 1.5          # 예전 기록 채우기: 요청 사이 간격
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
        self._request_backfill(title, artist, sid, info)
        return None

    def take_updated(self) -> bool:
        """마지막 호출 이후 새 커버가 저장됐는지 (화면을 다시 그릴지)."""
        with self._lock:
            updated, self._updated = self._updated, False
        return updated

    # -- 예약 ------------------------------------------------------------- #

    def remember(self, title: str, artist: str, song_id: str, url: str) -> None:
        """가사 검색에서 알게 된 곡 ID·커버 주소를 기록하고 커버를 받습니다."""
        if not (isinstance(song_id, str) and _SONG_ID.match(song_id) and valid_cover_url(url)):
            return
        key = _key(title, artist)
        with self._lock:
            self._index[key] = {"song_id": song_id, "url": url}
            self._queued.add(key)
        self._jobs.put(("download", key, song_id, url))

    def _request_backfill(self, title: str, artist: str, sid, info) -> None:
        if not title or (artist or "").strip() in ("", "Unknown"):
            return
        key = _key(title, artist)
        with self._lock:
            if key in self._queued:
                return
            if info and info.get("miss") and time.time() - info["miss"] < _MISS_RETRY_SEC:
                return
            self._queued.add(key)
        if info and info.get("song_id") and valid_cover_url(info.get("url")):
            self._jobs.put(("download", key, info["song_id"], info["url"]))
        else:
            self._jobs.put(("resolve", key, title, artist))

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
            try:
                if job[0] == "download":
                    _, key, sid, url = job
                    self._download(fetcher, sid, url)
                else:
                    _, key, title, artist = job
                    time.sleep(_BACKFILL_GAP_SEC)
                    rows = parse_search_rows(fetcher._get_text(
                        "https://www.melon.com/search/song/index.htm?q=" + quote(search_query_for(title, artist))))
                    best, _score = pick_best_row(rows, title, artist)
                    if best is None:
                        self._mark_miss(key)
                        continue
                    sid = best[0]
                    time.sleep(_BACKFILL_GAP_SEC)
                    soup = BeautifulSoup(fetcher._get_text(
                        f"https://www.melon.com/song/detail.htm?songId={sid}"), "html.parser")
                    url = cover_url_from_detail(soup)
                    if not url:
                        self._mark_miss(key)
                        continue
                    with self._lock:
                        self._index[key] = {"song_id": sid, "url": url}
                    self._download(fetcher, sid, url)
            except Exception as e:
                print(f"[⚠️] 앨범 커버를 가져오지 못했습니다: {e}")
                self._mark_miss(job[1])

    def _mark_miss(self, key: str) -> None:
        with self._lock:
            self._index[key] = {"miss": time.time()}
            self._save_index()

    def _download(self, fetcher, sid: str, url: str) -> None:
        path = self._file(sid)
        if not os.path.exists(path):
            res = fetcher.session.get(url + _RESIZE, headers=fetcher.headers, timeout=(5, 10), stream=True)
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
