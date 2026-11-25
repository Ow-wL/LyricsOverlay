"""업데이트 설치 (exe로 실행 중일 때만).

흐름 — 원래 exe는 마지막 순간(원자적 교체)까지 그대로 둡니다:
  1) [기존 앱, 작업 스레드] 새 exe를 현재 exe 옆에 임시 이름(무작위, 배타 생성)으로 받으며 SHA-256 계산.
     GitHub가 계산한 자산 digest와 크기가 정확히 맞아야 합니다. 리다이렉트는 허용 호스트만 따라갑니다.
  2) [기존 앱] 임시 파일을 다시 읽어 해시를 한 번 더 확인하고, 그 파일을
     '--apply-update <대상 exe> --wait-pids <pid들>' 인자로 실행한 뒤 정상 종료 절차를 밟습니다.
  3) [새 exe, 적용 모드] 기존 앱과 PyInstaller 부모 프로세스가 끝날 때까지 기다린 뒤,
     원래 exe를 '.previous'로 복사해 두고, 자기 자신을 대상 옆에 복사한 다음 os.replace로 한 번에 교체합니다.
     그리고 교체된 exe를 '--updated-from <이전 버전>'으로 실행하고 끝납니다.
  4) [교체된 새 앱] 메인 루프까지 정상으로 올라오면 임시 파일과 '.previous'를 지웁니다.
     새 버전이 시작하지 못하면 '.previous'가 남아 있어 손으로 되돌릴 수 있습니다.

남은 위험: 코드 서명이 없으므로, GitHub 계정이 탈취돼 악성 릴리스가 올라오면 막을 수 없습니다
(브라우저로 직접 받아도 같은 위험). 인증서가 생기면 서명 검증을 추가하세요.
"""

import ctypes
import hashlib
import os
import secrets
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit

import requests  # type: ignore

from core.updater import _HEADERS, _MAX_EXE_BYTES, EXE_ASSET_NAME, ReleaseInfo

# GitHub 릴리스 파일이 실제로 내려오는 호스트 (리다이렉트로 이어지는 곳)
_ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
_MAX_REDIRECTS = 5
_DOWNLOAD_DEADLINE_SEC = 30 * 60


class UpdateError(Exception):
    pass


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_exe() -> str:
    return os.path.realpath(sys.executable)


def backup_path(target: str) -> str:
    return target + ".previous"


# ------------------------------------------------------------------ #
# 1) 내려받기
# ------------------------------------------------------------------ #

def _open_following_redirects(url: str):
    """허용된 https 호스트로만 리다이렉트를 따라가며 응답을 엽니다 (요청을 보내기 전에 매번 검사)."""
    session = requests.Session()
    for _ in range(_MAX_REDIRECTS + 1):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in _ALLOWED_HOSTS:
            raise UpdateError(f"허용되지 않은 주소로 연결하려 해서 중단했어요 ({parts.hostname}).")
        res = session.get(url, headers=_HEADERS, timeout=(10, 30), stream=True, allow_redirects=False)
        if res.status_code in (301, 302, 303, 307, 308):
            location = res.headers.get("Location", "")
            res.close()
            url = urljoin(url, location)
            continue
        res.raise_for_status()
        return res
    raise UpdateError("리다이렉트가 너무 많아 중단했어요.")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(info: ReleaseInfo, progress, cancelled) -> str:
    """(작업 스레드) 새 exe를 받아 검증한 임시 파일 경로를 돌려줍니다. 실패하면 UpdateError.

    progress(받은 바이트, 전체)를 수시로 부르고, cancelled()가 True면 다음 조각에서 멈춥니다.
    """
    if not info.can_auto_update:
        raise UpdateError("이 릴리스는 자동 업데이트를 할 수 없어요 (검증값 없음).")
    folder = os.path.dirname(current_exe())
    dest = os.path.join(folder, f"LyricsOverlay.update-{secrets.token_hex(6)}.exe")
    start = time.monotonic()
    h = hashlib.sha256()
    received = 0
    try:
        f = open(dest, "xb")  # 같은 이름이 있으면 실패 (다른 파일을 덮어쓰지 않음)
    except OSError as e:
        raise UpdateError(f"프로그램 폴더에 파일을 쓸 수 없어요. 릴리스 페이지에서 직접 받아 주세요. ({e})")
    try:
        with f, _open_following_redirects(info.exe_url) as res:
            for chunk in res.iter_content(256 * 1024):
                if cancelled():
                    raise UpdateError("업데이트를 취소했어요.")
                if time.monotonic() - start > _DOWNLOAD_DEADLINE_SEC:
                    raise UpdateError("내려받는 데 너무 오래 걸려 중단했어요.")
                received += len(chunk)
                if received > info.exe_size or received > _MAX_EXE_BYTES:
                    raise UpdateError("받은 파일이 예상보다 커서 중단했어요.")
                h.update(chunk)
                f.write(chunk)
                progress(received, info.exe_size)
            f.flush()
            os.fsync(f.fileno())
        if received != info.exe_size:
            raise UpdateError("파일을 끝까지 받지 못했어요.")
        if h.hexdigest() != info.exe_sha256:
            raise UpdateError("받은 파일의 검증값(SHA-256)이 맞지 않아 설치하지 않았어요.")
        with open(dest, "rb") as g:
            if g.read(2) != b"MZ":
                raise UpdateError("받은 파일이 Windows 실행 파일이 아니에요.")
        return dest
    except BaseException:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise


# ------------------------------------------------------------------ #
# 2) 새 exe에 교체를 맡기기 (기존 앱, 종료 직전)
# ------------------------------------------------------------------ #

def _clean_env() -> dict:
    """PyInstaller가 바꾼 환경(_MEIPASS 관련)을 새 프로세스에 물려주지 않습니다."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def hand_off(staged: str, expected_sha256: str, previous_version: str) -> None:
    """검증한 임시 exe를 '적용 모드'로 실행합니다. 이 함수 뒤에 기존 앱은 곧바로 종료해야 합니다."""
    if _sha256_file(staged) != expected_sha256:  # 받은 뒤 바뀌지 않았는지 한 번 더
        raise UpdateError("임시 파일이 바뀌어 설치를 중단했어요.")
    pids = [os.getpid()]
    try:
        pids.append(os.getppid())  # onefile 부트로더 부모 프로세스
    except Exception:
        pass
    args = [
        staged, "--apply-update", current_exe(),
        "--previous-version", previous_version,
        "--wait-pids", ",".join(str(p) for p in pids),
    ]
    subprocess.Popen(
        args, cwd=os.path.dirname(current_exe()), env=_clean_env(), close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


# ------------------------------------------------------------------ #
# 3) 적용 모드 (새 exe가 임시 이름으로 실행된 상태)
# ------------------------------------------------------------------ #

def _wait_pids(pids: list[int], timeout_sec: float) -> bool:
    SYNCHRONIZE = 0x00100000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    deadline = time.monotonic() + timeout_sec
    for pid in pids:
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            continue  # 이미 끝남
        try:
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            if kernel32.WaitForSingleObject(handle, remaining) != 0:  # WAIT_OBJECT_0
                return False
        finally:
            kernel32.CloseHandle(handle)
    return True


def _log(folder: str, text: str) -> None:
    try:
        with open(os.path.join(folder, "LyricsOverlay.update.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except OSError:
        pass


def run_apply_mode(argv: list[str]) -> int:
    """'--apply-update' 인자로 실행됐을 때: 기존 exe를 자기 자신으로 바꾸고 새로 띄웁니다."""
    def arg(name: str) -> str:
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else ""

    me = current_exe()
    target = os.path.realpath(arg("--apply-update"))
    folder = os.path.dirname(target)
    # 같은 폴더의 LyricsOverlay.exe만 교체합니다 (경로 조작 방지)
    if os.path.basename(target) != EXE_ASSET_NAME or os.path.dirname(me) != folder:
        _log(os.path.dirname(me), f"교체 대상이 올바르지 않아 중단: {target}")
        return 2
    pids = [int(p) for p in arg("--wait-pids").split(",") if p.strip().isdigit()]
    if not _wait_pids(pids, 60):
        _log(folder, "기존 프로그램이 끝나지 않아 교체하지 않음")
        return 3
    backup = backup_path(target)
    tmp = os.path.join(folder, f"LyricsOverlay.replacing-{secrets.token_hex(6)}.exe")
    try:
        import shutil
        if os.path.exists(target):
            shutil.copy2(target, backup)        # 되돌릴 수 있게 이전 버전 보관
        shutil.copy2(me, tmp)                   # 같은 폴더(같은 볼륨)에 새 버전 복사
        for attempt in range(20):               # 보안 프로그램 등이 잠깐 잡고 있을 수 있어 재시도
            try:
                os.replace(tmp, target)         # 원자적 교체: 실패해도 원래 exe는 그대로
                break
            except PermissionError:
                time.sleep(0.5)
        else:
            raise UpdateError("기존 실행 파일을 바꿀 수 없었어요")
    except Exception as e:
        _log(folder, f"교체 실패, 이전 버전 유지: {e}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        subprocess.Popen([target], cwd=folder, env=_clean_env(), close_fds=True)  # 원래 버전이라도 다시 켬
        return 4
    _log(folder, f"교체 완료 ({arg('--previous-version')} → 새 버전)")
    subprocess.Popen(
        [target, "--updated-from", arg("--previous-version"), "--cleanup", me],
        cwd=folder, env=_clean_env(), close_fds=True,
    )
    return 0


# ------------------------------------------------------------------ #
# 4) 정리 (교체된 새 앱이 정상으로 올라온 뒤)
# ------------------------------------------------------------------ #

def cleanup_after_update(argv: list[str]) -> None:
    """업데이트 뒤 남은 임시 파일과 이전 버전 백업을 지웁니다. 지우지 못하면 다음 실행 때 다시 시도."""
    if not is_frozen():
        return
    me = current_exe()
    folder = os.path.dirname(me)
    candidates = []
    if "--cleanup" in argv and argv.index("--cleanup") + 1 < len(argv):
        candidates.append(os.path.realpath(argv[argv.index("--cleanup") + 1]))
    try:
        for name in os.listdir(folder):
            if name.startswith(("LyricsOverlay.update-", "LyricsOverlay.replacing-")) and name.endswith(".exe"):
                candidates.append(os.path.join(folder, name))
    except OSError:
        pass
    candidates.append(backup_path(me))
    for path in candidates:
        if os.path.dirname(path) != folder or os.path.realpath(path) == me:
            continue
        for _ in range(10):  # 적용 프로세스가 막 끝나는 중일 수 있음
            try:
                if os.path.exists(path):
                    os.remove(path)
                break
            except OSError:
                time.sleep(0.5)
