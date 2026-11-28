import sys
import os

def resource_path(relative_path: str) -> str:
    """
    PyInstaller에 의해 패키징되었을 때와 일반 실행 시의 경로를 모두 지원하는 함수입니다.
    패키징된 경우 임시 폴더(sys._MEIPASS)의 경로를 반환하고, 일반 실행 시 원본 경로를 반환합니다.
    """
    try:
        # PyInstaller는 런타임에 임시 폴더를 생성하고 경로를 _MEIPASS에 저장합니다.
        base_path = sys._MEIPASS
    except AttributeError:
        # 일반 실행 환경
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def state_dir() -> str:
    r"""사용자별 고정 폴더 (%LOCALAPPDATA%\LyricsOverlay). 데이터 폴더와 달리 설정이나 환경 변수로 바뀌지 않습니다.

    멜론 창 복구 기록과 진단 로그처럼, 데이터 폴더를 바꿔도 같은 자리에서 찾아야 하는 파일을 둡니다.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "LyricsOverlay")


def atomic_write_json(path: str, data) -> None:
    """JSON을 임시 파일에 먼저 쓴 뒤 교체해, 저장 중 중단돼도 기존 파일이 깨지지 않게 합니다."""
    import json
    import tempfile

    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(
        prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
