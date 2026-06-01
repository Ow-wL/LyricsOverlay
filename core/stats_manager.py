import json
import os
import time

STATS_FILE_PATH = "lyrics_stats.json"


def load_stats() -> dict:
    """파일에서 통계 데이터를 로드합니다."""
    default_stats = {
        "play_history": [],  # [{"title": str, "artist": str, "timestamp": str}, ...]
        "total_lines": 0,
        "total_play_time_sec": 0,
        "theme": "light"
    }
    if os.path.exists(STATS_FILE_PATH):
        try:
            with open(STATS_FILE_PATH, "r", encoding="utf-8") as f:
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

            # 누락된 필드 보정
            for key, val in default_stats.items():
                if key not in data:
                    data[key] = val
            return data
        except Exception as e:
            print(f"[⚠️] 통계 로드 실패: {e}")
    return default_stats


def save_stats(stats: dict) -> None:
    """통계 데이터를 파일에 저장합니다."""
    try:
        with open(STATS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[⚠️] 통계 저장 실패: {e}")


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
