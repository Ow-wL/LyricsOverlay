"""멜론의 재생 상태 읽기 (Windows 미디어 세션, SMTC).

멜론은 Windows의 '미디어 제어'에 재생/일시정지 상태와 곡 길이·시작 시점을 알려 줍니다.
이걸로 실제로 재생 중인 시간만 감상 시간으로 세고, 같은 곡을 다시 처음부터 틀었는지도 알아냅니다.
세션을 찾지 못하면 available=False로 두고, 호출하는 쪽이 예전 방식(창이 보이면 재생 중)으로 대신합니다.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

try:
    from winsdk.windows.media.control import (  # type: ignore
        GlobalSystemMediaTransportControlsSessionManager as _Manager,
    )
except Exception:  # winsdk에 해당 모듈이 없는 환경
    _Manager = None

_PLAYING = 4  # GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING


@dataclass
class MediaState:
    available: bool = False          # 멜론 미디어 세션을 찾았는지
    playing: bool = False            # 재생 중인지 (available일 때만 의미 있음)
    position_sec: float = 0.0        # 멜론이 마지막으로 알려 준 재생 위치
    duration_sec: float = 0.0        # 곡 길이 (모르면 0)
    track_start: datetime | None = None  # 곡이 처음부터 재생되기 시작한 시각 (추정)


class MelonMediaSession:
    def __init__(self):
        self._manager = None
        self._failed = False
        self.state = MediaState()

    async def poll(self) -> MediaState:
        """현재 상태를 읽어 self.state에 담고 돌려줍니다. 실패해도 예외를 내지 않습니다."""
        if _Manager is None or self._failed:
            self.state = MediaState()
            return self.state
        try:
            if self._manager is None:
                self._manager = await _Manager.request_async()
            session = None
            for s in self._manager.get_sessions():
                if "melon" in (s.source_app_user_model_id or "").lower():
                    session = s
                    break
            if session is None:
                self.state = MediaState()
                return self.state
            info = session.get_playback_info()
            tl = session.get_timeline_properties()
            position = tl.position.total_seconds()
            updated = tl.last_updated_time
            if updated is not None and updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            start = None
            if updated is not None and updated.year > 1601:
                from datetime import timedelta
                start = updated - timedelta(seconds=position)
            self.state = MediaState(
                available=True,
                playing=info.playback_status == _PLAYING,
                position_sec=position,
                duration_sec=tl.end_time.total_seconds(),
                track_start=start,
            )
        except Exception as e:
            print(f"[⚠️] 미디어 세션을 읽지 못했습니다: {e}")
            self._failed = True  # 계속 실패하는 환경이면 더 시도하지 않음
            self.state = MediaState()
        return self.state


def is_restart(prev: MediaState, cur: MediaState, played_sec: float) -> bool:
    """같은 곡을 처음부터 다시 틀었는지 (반복 재생).

    멜론은 곡이 시작될 때 재생 위치(≈0)와 시각을 새로 알려 줍니다. 일시정지 후 다시 재생할 때도
    값이 바뀔 수 있으므로, 위치가 거의 처음이고 이미 곡의 절반 이상(또는 길이를 모르면 60초 이상)
    들은 경우에만 반복 재생으로 봅니다.
    """
    if not (prev.available and cur.available) or prev.track_start is None or cur.track_start is None:
        return False
    if cur.position_sec > 3:
        return False
    if abs((cur.track_start - prev.track_start).total_seconds()) < 5:
        return False
    need = cur.duration_sec * 0.5 if cur.duration_sec > 0 else 60
    return played_sec >= need
