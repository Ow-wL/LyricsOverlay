"""새 버전 확인 (GitHub 릴리스).

GitHub의 '최신 릴리스' 정보를 물어봐서 지금 버전보다 새 버전이 있으면 알려 줍니다.
네트워크 호출은 작업 스레드에서 하고, 메인 루프가 poll()로 결과를 가져갑니다
(가사 검색과 같은 방식: 이 앱은 exec() 대신 processEvents() 루프를 돌립니다).

보내는 정보: GitHub에 요청 한 번 (IP 주소와 'LyricsOverlay/<버전>' User-Agent). 개인 데이터는 보내지 않습니다.
"""

import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

import requests  # type: ignore

from core.version import APP_VERSION

REPO = "Ow-wL/LyricsOverlay"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
EXE_ASSET_NAME = "LyricsOverlay.exe"
CHECKSUM_ASSET_NAME = "LyricsOverlay.exe.sha256.txt"

_MAX_API_BYTES = 1024 * 1024
_MAX_EXE_BYTES = 400 * 1024 * 1024
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"LyricsOverlay/{APP_VERSION}",
}


def parse_version(tag: str) -> tuple[int, ...] | None:
    """'1.2.0', 'v1.10.3' → (1, 2, 0). 숫자.숫자(.숫자) 형식이 아니면 None."""
    if not isinstance(tag, str):
        return None
    m = re.fullmatch(r"[vV]?(\d+)\.(\d+)(?:\.(\d+))?", tag.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups(default="0"))


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    r, l = parse_version(remote), parse_version(local)
    return r is not None and l is not None and r > l


@dataclass
class ReleaseInfo:
    version: str                 # '1.2.0'
    html_url: str                # 릴리스 페이지
    notes: str                   # 변경 내용 (일반 텍스트로만 표시)
    exe_url: str | None = None   # LyricsOverlay.exe 다운로드 주소
    exe_size: int = 0
    exe_sha256: str | None = None  # GitHub가 계산한 자산 SHA-256 (소문자 16진수)
    checksum_url: str | None = None  # (예비) LyricsOverlay.exe.sha256.txt 자산

    @property
    def can_auto_update(self) -> bool:
        # 검증값은 GitHub가 계산한 자산 digest만 인정합니다. (같은 릴리스에 올린 .sha256.txt는
        # 같은 권한으로 함께 바꿀 수 있어 추가 보호가 거의 없습니다)
        return bool(self.exe_url and 0 < self.exe_size <= _MAX_EXE_BYTES and self.exe_sha256)


def _get_json(url: str) -> dict:
    with requests.get(url, headers=_HEADERS, timeout=(5, 10), stream=True) as res:
        res.raise_for_status()
        data, size = [], 0
        for chunk in res.iter_content(64 * 1024):
            size += len(chunk)
            if size > _MAX_API_BYTES:
                raise ValueError("응답이 너무 큽니다")
            data.append(chunk)
    import json
    return json.loads(b"".join(data).decode("utf-8"))


def _is_asset_url(url: str, version_tag: str) -> bool:
    """이 저장소·이 태그의 릴리스 파일 주소인지 (https://github.com/<repo>/releases/download/<tag>/<이름>)."""
    from urllib.parse import quote
    return url == f"https://github.com/{REPO}/releases/download/{quote(version_tag)}/{EXE_ASSET_NAME}"


def _is_github_url(url: str) -> bool:
    return isinstance(url, str) and url.startswith(f"https://github.com/{REPO}/")


def fetch_latest() -> ReleaseInfo | None:
    """최신 정식 릴리스 정보. 형식이 이상하면 None."""
    data = _get_json(LATEST_URL)
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    version = str(data.get("tag_name", "")).lstrip("vV")
    if parse_version(version) is None:
        return None
    html_url = data.get("html_url", "")
    info = ReleaseInfo(
        version=version,
        html_url=html_url if _is_github_url(html_url) else RELEASES_PAGE,
        notes=str(data.get("body") or "")[:4000],
    )
    exe_assets = [
        a for a in (data.get("assets") or [])
        if isinstance(a, dict) and a.get("name") == EXE_ASSET_NAME and a.get("state", "uploaded") == "uploaded"
    ]
    if len(exe_assets) == 1:  # 같은 이름이 여럿이면(비정상) 자동 업데이트를 하지 않습니다
        asset = exe_assets[0]
        url = asset.get("browser_download_url", "")
        digest = str(asset.get("digest") or "")
        if _is_asset_url(url, version_tag=str(data.get("tag_name", ""))):
            info.exe_url = url
            info.exe_size = int(asset.get("size") or 0)
            if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
                info.exe_sha256 = digest.split(":", 1)[1].lower()
    return info


class UpdateChecker:
    """주기적으로(또는 요청 시) 최신 버전을 확인합니다. 메인 루프에서 poll()을 부르세요."""

    FIRST_DELAY_SEC = 30
    INTERVAL_SEC = 24 * 3600

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="update")
        self._future: Future | None = None
        self._manual = False
        self._next_auto = time.monotonic() + self.FIRST_DELAY_SEC
        self.latest: ReleaseInfo | None = None

    def check_now(self) -> bool:
        """사용자가 '지금 확인'을 눌렀을 때. 자동 확인이 진행 중이면 그 결과를 수동 결과로 보여 줍니다."""
        self._manual = True
        if self._future is not None and not self._future.done():
            return True
        self._future = self._executor.submit(fetch_latest)
        return True

    def poll(self, auto_enabled: bool):
        """결과가 나왔으면 ('available'|'latest'|'error', ReleaseInfo|str|None, manual)을, 아니면 None."""
        now = time.monotonic()
        if self._future is None:
            if auto_enabled and now >= self._next_auto:
                self._next_auto = now + self.INTERVAL_SEC
                self._manual = False
                self._future = self._executor.submit(fetch_latest)
            return None
        if not self._future.done():
            return None
        future, self._future = self._future, None
        manual = self._manual
        try:
            info = future.result()
        except Exception as e:
            print(f"[⚠️] 업데이트 확인 실패: {e}")
            return ("error", str(e), manual)
        if info is None:
            return ("invalid", None, manual)
        if is_newer(info.version):
            self.latest = info
            return ("available", info, manual)
        return ("latest", info, manual)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


