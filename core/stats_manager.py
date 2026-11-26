import json
import os
import time

from core.utils import atomic_write_json

# 읽지 못한 통계 파일을 보관하지도 못했을 때, 기본값으로 덮어쓰지 않도록 저장을 막습니다.
_save_blocked: set[str] = set()

def get_stats_file_path(data_dir: str) -> str:
    return os.path.join(data_dir, "lyrics_stats.json")

def load_stats(data_dir: str) -> dict:
    """파일에서 통계 데이터를 로드합니다."""
    stats_file_path = get_stats_file_path(data_dir)
    default_stats = {
        "play_history": [],  # [{"title": str, "artist": str, "timestamp": str}, ...]
        "total_lines": 0,
        "total_play_time_sec": 0,
        "theme": "light"
    }
    if os.path.exists(stats_file_path):
        try:
            with open(stats_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 데이터 마이그레이션 (구버전 -> 신버전)
            if "songs" in data and "play_history" not in data:
                print("[🔄] 데이터 형식 마이그레이션 중...")
                data.setdefault("play_history", [])
                for song_info in data["songs"]:
                    if isinstance(song_info, list) and len(song_info) == 2:
                        full_title, date = song_info
                        if " - " in full_title:
                            parts = full_title.rsplit(" - ", 1)
                            title, artist = parts[0], parts[1]
                        else:
                            title, artist = full_title, "Unknown"
                        data["play_history"].append({
                            "title": title,
                            "artist": artist,
                            "timestamp": f"20{date.replace('.', '-')} 00:00:00"
                        })
                del data["songs"]

            return _sanitize_stats(data, default_stats)
        except Exception as e:
            print(f"[⚠️] 통계 로드 실패: {e}")
            # 깨진 파일을 따로 보관해, 이후 저장이 기존 기록을 덮어쓰지 않게 합니다.
            backup_path = (
                f"{stats_file_path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 10**9}"
            )
            try:
                os.replace(stats_file_path, backup_path)
                print(f"[🧯] 손상된 통계 파일을 보관했습니다: {backup_path}")
            except Exception as backup_err:
                print(f"[⚠️] 손상된 통계 파일 보관 실패, 이번 실행에서는 저장하지 않습니다: {backup_err}")
                _save_blocked.add(os.path.abspath(stats_file_path))
    return default_stats


def _sanitize_entry(entry) -> dict | None:
    """감상 기록 한 건을 검사합니다. 제목이 없으면 버리고, 나머지는 기본값으로 채웁니다."""
    if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
        return None
    clean = dict(entry)
    if not isinstance(clean.get("artist"), str):
        clean["artist"] = "Unknown"
    ts = clean.get("timestamp")
    try:
        time.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        clean["timestamp"] = "1970-01-01 00:00:00"
    sid = clean.get("song_id")
    if not (isinstance(sid, str) and sid.isdigit() and 5 <= len(sid) <= 12):
        clean.pop("song_id", None)
    for key in ("play_time_sec", "lines"):
        v = clean.get(key, 0)
        clean[key] = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else 0
    return clean


def _sanitize_stats(data, default_stats: dict) -> dict:
    """형식이 틀린 필드는 기본값으로 바꿔, 손상된 값 하나로 앱이 시작하다 죽지 않게 합니다."""
    if not isinstance(data, dict):
        raise ValueError("통계 파일 형식이 올바르지 않습니다")
    history = data.get("play_history")
    if not isinstance(history, list):
        history = []
    data["play_history"] = [e for e in (_sanitize_entry(x) for x in history) if e is not None]
    for key in ("total_lines", "total_play_time_sec"):
        v = data.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            data[key] = default_stats[key]
    if data.get("theme") not in ("light", "dark"):
        data["theme"] = default_stats["theme"]
    return data


def save_stats(stats: dict, data_dir: str) -> bool:
    """통계 데이터를 파일에 저장합니다. 성공하면 True."""
    stats_file_path = get_stats_file_path(data_dir)
    if os.path.abspath(stats_file_path) in _save_blocked:
        return False
    try:
        atomic_write_json(stats_file_path, stats)
        return True
    except Exception as e:
        print(f"[⚠️] 통계 저장 실패: {e}")
        return False


def parse_song_info(full_title: str) -> tuple[str, str]:
    """창 제목에서 곡 제목과 가수를 분리합니다."""
    if " - " in full_title:
        parts = full_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return full_title.strip(), "Unknown"


def make_session_stats(persistent_stats: dict) -> dict:
    """세션 통계 초기값을 생성합니다."""
    return {
        "play_count": 0,
        "lines": persistent_stats.get("total_lines", 0),
        "session_lines": 0,
        "base_play_time": persistent_stats.get("total_play_time_sec", 0),
        "start_time": time.time()
    }
