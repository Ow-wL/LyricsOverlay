"""
LyricsOverlay — 엔트리 포인트
실행: python main.py
"""

import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
import sys
import time
import os
import ctypes

# 콘솔 출력이 파이프/cp949일 때 이모지 로그 하나로 프로그램이 죽지 않도록 합니다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

if os.name == 'nt':
    try:
        from core.version import APP_USER_MODEL_ID
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass

# 이 앱은 작은 이미지(가사 영역)만 다룹니다. numpy(OpenBLAS)·OpenCV가 CPU 코어 수만큼 스레드와
# 메모리를 미리 잡지 않게 1개로 묶습니다. (16코어 PC에서 numpy만으로 약 490MB·15스레드를 잡던 것이 13MB로)
# numpy·cv2를 import하기 전에 설정해야 효과가 있습니다.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import cv2
cv2.setNumThreads(1)
from PySide6.QtWidgets import QApplication, QMessageBox  # type: ignore

from core import app_log, autostart, covers, melon_control, melon_http
from core.hotkey_manager import HotkeyManager, send_next_track, send_play_pause, send_prev_track
from core.ocr_engine import OCR_HELP, OCR_KOREAN, OCR_STATUS, ocr_available, windows_native_ocr_split
from core.stats_manager import load_stats, make_session_stats, parse_song_info, resumable_entry, save_stats
from core.window_capture import (
    WindowStyleGuard, capture_covered_window, find_melon_window, is_melon_minimized, recheck_window,
)
from gui.main_window import MainWindow
from lyrics.matcher import LyricMatcher
from core.app_config import AppConfig
from core.media_session import MediaState, MelonMediaSession, is_restart
from core.single_instance import SingleInstance
from core.updater import UpdateChecker
from core.version import APP_VERSION
from overlay.config_manager import OverlayConfigManager

# ------------------------------------------------------------------ #
# 전역 상태
# ------------------------------------------------------------------ #
log_history: list[str] = []
is_running: bool = True
_window: MainWindow | None = None

persistent_stats: dict = {}
session_stats: dict = {}
_app_config: AppConfig | None = None

# 전역 단축키(keyboard 스레드)에서 메인 스레드로 넘길 작업
_pending_actions: "queue.SimpleQueue" = queue.SimpleQueue()

# 가사 인식 주기 (초). 가사는 몇 초에 한 번 바뀌므로 화면 갱신(0.05초)보다 느리게 읽어 CPU를 아낍니다.
OCR_INTERVAL = 0.2
# 멜론 창 전체 재탐색 주기 (초). 그 사이에는 찾아 둔 창이 유효한지만 확인합니다.
WINDOW_RESCAN_INTERVAL = 1.0
# 멜론 창 캡처는 멜론이 응답해야 끝나므로 별도 스레드에서 하고, 이 시간이 넘으면 이번 회차는 건너뜁니다.
CAPTURE_TIMEOUT = 1.5
_capture_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capture")


def recognition_idle_reason(
    media_available: bool, media_playing: bool, overlay_visible: bool, window_visible: bool
) -> str:
    """가사 인식을 쉬어도 되면 그 이유(대시보드 표시용), 계속해야 하면 빈 문자열.

    - 멜론이 일시정지 중이면 가사가 바뀌지 않으므로 쉽니다. (재생 상태를 모르면 계속)
    - 오버레이를 숨겼고 메인 창도 보이지 않으면, 가사를 볼 곳이 없으므로 쉽니다.
    """
    if media_available and not media_playing:
        return "일시정지 중이라 가사 인식을 쉬고 있어요"
    if not overlay_visible and not window_visible:
        return "오버레이가 꺼져 있어 가사 인식을 쉬고 있어요"
    return ""


def _drain_pending_actions() -> None:
    """단축키 콜백은 keyboard 스레드에서 들어오므로, 실제 처리는 메인 스레드에서 합니다."""
    while True:
        try:
            action = _pending_actions.get_nowait()
        except queue.Empty:
            return
        action()


# ------------------------------------------------------------------ #
# 로그
# ------------------------------------------------------------------ #

def add_log(message: str) -> None:
    """최근 5개 로그를 유지하며 GUI 리스트에도 연동합니다."""
    global log_history, _window
    timestamp = time.strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    log_history.append(log_msg)
    app_log.write(message)
    if len(log_history) > 5:
        log_history.pop(0)

    if _window:
        _window.dashboard_page.log_list.addItem(log_msg)
        if _window.dashboard_page.log_list.count() > 50:
            _window.dashboard_page.log_list.takeItem(0)
        _window.dashboard_page.log_list.scrollToBottom()


# ------------------------------------------------------------------ #
# 단축키 콜백
# ------------------------------------------------------------------ #

def _on_toggle_mode() -> None:
    if _window is None:
        return
    cfg: OverlayConfigManager = _window.config_manager
    if _window.overlay.editing:
        _window.finish_overlay_edit()  # 위치 조정 중 F9 → 조정을 끝내고 원래 모드로
        return
    cfg.set_ghost_mode(not cfg.ghost_mode)
    _window.sync_controls()  # 대시보드·설정 화면 스위치도 함께 맞춤
    mode_name = "반투명 + 클릭통과" if cfg.ghost_mode else "불투명 + 클릭가능"
    print(f"\n[🔔] 모드 전환: {mode_name}")
    add_log(f"모드 전환: {mode_name}")


def _on_quit() -> None:
    global is_running
    is_running = False
    print("\n[🔔] 프로그램 종료 요청됨.")
    add_log("프로그램 종료 요청됨")
    QApplication.quit()


# ------------------------------------------------------------------ #
# 메인 루프
# ------------------------------------------------------------------ #

def roi_unchanged(prev, cur, tolerance: float = 0.6) -> bool:
    """가사 영역 그림이 지난번과 (거의) 같은지. 같으면 OCR을 다시 할 필요가 없습니다."""
    if prev is None or prev.shape != cur.shape:
        return False
    if (prev == cur).all():
        return True
    return float(cv2.absdiff(prev, cur).mean()) < tolerance  # 압축·안티앨리어싱 잡음 정도는 같은 것으로


def is_song_title(title: str) -> bool:
    """멜론 창 제목이 곡('제목 - 가수')인지. 곡이 없을 때는 '멜론 PC 플레이어' 같은 제목이 됩니다."""
    title = (title or "").strip()
    if " - " not in title:
        return False
    name, _, artist = title.rpartition(" - ")
    return bool(name.strip()) and bool(artist.strip())


def link_song(song_info: dict, searcher, window_title: str) -> tuple[bool, str | None]:
    """가사 검색이 알아낸 멜론 곡 ID를 기록에 붙이고, 커버 주소를 알게 됐으면 돌려줍니다.

    Returns (곡 ID를 이번에 붙이거나 바로잡았는지, 커버 주소 또는 None)

    곡 ID는 검색이 끝나면 바로 알지만, 커버 주소는 그 뒤 곡 페이지를 받아야(요청 간격 때문에 1초 이상 뒤)
    알게 됩니다. 그래서 곡 ID를 붙인 뒤에도 커버 주소가 올 때까지 계속 불러야 합니다.
    """
    sid = searcher.song_id_for(window_title)
    if not sid:
        return False, None
    playing = parse_song_info(window_title.replace(" - Melon", "").strip())
    if playing != (song_info["title"], song_info["artist"]):
        return False, None  # 창 제목이 이미 다음 곡으로 바뀜
    # 이어 듣는 기록에 예전 곡 ID가 있어도, 이번에 확인한 곡 ID와 다르면 바로잡습니다.
    added = song_info.get("song_id") != sid
    if added:
        song_info["song_id"] = sid
    return added, searcher.cover_for(window_title)


async def main() -> None:
    global _window, is_running, persistent_stats, session_stats, _app_config

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 창을 트레이로 숨겨도 계속 실행

    # 이미 실행 중이면 그 창을 앞으로 불러오고 끝냅니다.
    instance = SingleInstance()
    if not instance.acquire():
        print("[ℹ️] 이미 실행 중입니다. 기존 창을 엽니다.")
        return
    
    _app_config = AppConfig()

    # 진단 로그: 설정에서 끄거나 '감상 기록 저장'을 끄면 남기지 않습니다 (곡 제목이 들어가므로).
    app_log.start(should_log=lambda: _app_config.diagnostic_log and _app_config.record_history)
    # 지난 실행에서 멜론 요청을 쉬는 중이었다면 이어서 쉽니다 (앱을 다시 켠다고 바로 요청하지 않게).
    melon_http.restore_pause(*_app_config.melon_pause)

    # 지난번 강제 종료로 투명하게 남은 멜론 창이 있으면 가장 먼저 복구합니다.
    # (이후 단계에서 무엇이 실패해도 멜론 창은 원래대로 돌아오게)
    # 복구 기록은 데이터 폴더와 무관한 고정 폴더에 둡니다. 예전 버전은 데이터 폴더에 적었으므로 거기도 읽습니다.
    style_guard = WindowStyleGuard(legacy_dirs=(_app_config.data_dir,))
    try:
        recovered = style_guard.recover_from_file()
    except Exception as e:  # 복구가 실패해도 앱 시작은 막지 않습니다
        print(f"[⚠️] 이전 실행의 창 상태 복구 실패: {e}")
        recovered = 0

    persistent_stats = load_stats(_app_config.data_dir)
    session_stats = make_session_stats(persistent_stats)

    # 메인 윈도우 생성
    initial_theme = persistent_stats.get("theme", "light")
    window = MainWindow(stats=persistent_stats, app_config=_app_config, initial_theme=initial_theme)
    _window = window

    # 테마 저장
    def on_theme_changed(theme_name: str) -> None:
        persistent_stats["theme"] = theme_name
        save_stats(persistent_stats, _app_config.data_dir)
        add_log(f"테마 변경: {theme_name}")

    window.theme_changed.connect(on_theme_changed)

    def on_window_closed() -> None:
        global is_running
        is_running = False
        print("\n[🔔] GUI 종료 감지. 백그라운드 루프 중지...")

    window.window_closed.connect(on_window_closed)
    window.quit_requested.connect(_on_quit)
    instance.activate_requested.connect(window.show_from_tray)

    # 히스토리 목록 초기화
    window.music_page.set_history(persistent_stats.get("play_history", []))

    # Windows 시작 시 자동 실행이면 창 없이 트레이로 시작합니다 (트레이가 없으면 창을 띄움).
    autostart.sync_path()
    if autostart.launched_by_autostart(sys.argv) and window.tray is not None:
        window.hide()
    else:
        window.show()

    overlay = window.overlay
    config_manager = window.config_manager
    matcher = LyricMatcher()

    # 재생 명령 (버튼·단축키 공통): 멜론 세션에 한 번만 보내고, 안 되면 미디어 키로 대신합니다.
    media_labels = {"prev": "이전 곡", "play_pause": "재생/일시정지", "next": "다음 곡"}
    media_fallback = {"prev": send_prev_track, "play_pause": send_play_pause, "next": send_next_track}
    last_media_cmd = {"key": "", "at": 0.0}
    media_tasks: set = set()  # 실행 중인 명령 작업 (참조를 잡아 두어 중간에 사라지지 않게)

    def send_media_command(key: str) -> None:
        now_ = time.monotonic()
        # 더블 클릭·키 반복으로 같은 명령이 연달아 오면 한 번만 처리
        if key == last_media_cmd["key"] and now_ - last_media_cmd["at"] < 0.35:
            return
        last_media_cmd.update(key=key, at=now_)

        async def run() -> None:
            # 1) 멜론 창에 직접 (멜론만, 한 번)  2) 미디어 세션  3) Windows 미디어 키
            how = ""
            if not melon_control.send_app_command(key):
                if await media.control(key):
                    how = " (미디어 세션)"
                else:
                    media_fallback[key]()
                    how = " (미디어 키)"
            add_log(f"미디어 제어: {media_labels.get(key, key)}{how}")

        task = asyncio.get_running_loop().create_task(run())
        media_tasks.add(task)
        task.add_done_callback(media_tasks.discard)

    # 단축키 매니저
    hotkey_mgr = HotkeyManager(
        on_ghost_toggle=lambda: _pending_actions.put(_on_toggle_mode),
        on_quit=lambda: _pending_actions.put(_on_quit),
        # 단축키는 별도 스레드에서 오므로 메인 루프로 넘겨서 처리합니다.
        on_media=lambda action: _pending_actions.put(lambda: send_media_command(action)),
    )

    def refresh_hotkeys() -> None:
        hotkey_mgr.refresh(
            config_manager.hotkey_ghost,
            config_manager.hotkey_quit,
            hotkey_next=config_manager.hotkey_next,
            hotkey_prev=config_manager.hotkey_prev,
            hotkey_pause=config_manager.hotkey_pause,
            log_fn=add_log,
        )

    window.setting_page.hotkeys_changed.connect(refresh_hotkeys)
    refresh_hotkeys()

    # 재생 버튼 (대시보드 / 오버레이)
    def on_media_action(key: str) -> None:
        send_media_command(key)
    window.dashboard_page.media_controls.action_triggered.connect(on_media_action)
    overlay.media_controls.action_triggered.connect(on_media_action)
    
    # 대시보드 통계 초기 업데이트
    window.dashboard_page.update_stats(session_stats, persistent_stats.get("play_history", []))

    print("=" * 50)
    print("🎤 가사 대시보드 및 오버레이 실행 중")
    print("=" * 50)
    add_log("프로그램 시작")


    # 데이터 경로가 바뀌면 통계·설정·창 복구 기록을 모두 새 경로로 옮깁니다.
    def on_data_dir_changed(new_dir: str) -> None:
        save_stats(persistent_stats, new_dir)
        add_log(f"데이터 경로 변경: {new_dir}")

    _app_config.add_listener(config_manager.set_data_dir)
    _app_config.add_listener(on_data_dir_changed)

    # 앨범 커버 (데이터 폴더/covers). 화면은 core.covers.store를 통해 커버를 찾습니다.
    covers.store = covers.CoverStore(_app_config.data_dir)
    covers.store.enabled = _app_config.melon_covers
    _app_config.add_listener(covers.store.set_data_dir)
    matcher.searcher.enabled = _app_config.melon_lyrics
    sp = window.setting_page

    def refresh_covers_status(notice: str = "") -> None:
        left = covers.store.backfill_left
        paused = melon_http.pause_text()
        if paused:
            text = paused + "이에요."
        elif notice:
            text = notice
        elif left:
            text = f"예전 기록 커버를 찾는 중이에요 (남은 곡 {left}개)."
        else:
            text = f"받아 둔 커버 {covers.store.file_count()}개"
        sp.set_covers_status(text, backfilling=bool(left))

    def on_melon_lyrics(on: bool) -> None:
        _app_config.melon_lyrics = on
        matcher.searcher.enabled = on
        add_log(f"멜론 가사 가져오기: {'켬' if on else '끔'}")

    def on_melon_covers(on: bool) -> None:
        _app_config.melon_covers = on
        covers.store.enabled = on
        if not on:
            covers.store.cancel_backfill()
        add_log(f"앨범 커버 받기: {'켬' if on else '끔'}")
        refresh_covers_status()

    def on_backfill() -> None:
        wait = covers.store.backfill_wait()
        n, left_over = covers.store.backfill(persistent_stats.get("play_history", []))
        if n:
            more = f" (남은 {left_over}곡은 {covers.BACKFILL_COOLDOWN_SEC // 60}분 뒤에 다시 눌러 주세요)" if left_over else ""
            add_log(f"예전 기록 커버 채우기: 최근 곡부터 {n}곡 예약{more}")
        elif left_over and melon_http.paused_for() > 0:
            add_log(f"예전 기록 커버 채우기: {melon_http.pause_text()}이에요")
        elif left_over and wait > 0:
            # 멜론에 요청이 몰리지 않도록 한 번에 조금씩만 받습니다.
            add_log(f"예전 기록 커버 채우기: {int(wait) // 60 + 1}분 뒤에 다시 눌러 주세요 (남은 곡 {left_over}개)")
        else:
            add_log("예전 기록 커버 채우기: 찾을 곡이 없어요")
        refresh_covers_status(notice=(
            f"조금씩 받는 중이에요. {int(wait) // 60 + 1}분 뒤에 다시 눌러 주세요 (남은 곡 {left_over}개)."
            if not n and left_over and wait > 0 else ""
        ))

    def on_clear_covers() -> None:
        if QMessageBox.question(window, "받은 커버 지우기",
                                "받아 둔 앨범 커버를 모두 지울까요? 감상 기록은 그대로예요.") != QMessageBox.Yes:
            return
        n = covers.store.clear()
        window.refresh_covers()
        add_log(f"받은 커버 지움 ({n}개 파일)")
        refresh_covers_status()

    sp.melon_lyrics_toggled.connect(on_melon_lyrics)
    sp.melon_covers_toggled.connect(on_melon_covers)
    def on_auto_backfill(on: bool) -> None:
        _app_config.auto_backfill = on
        add_log(f"예전 기록 커버 자동 채우기: {'켬' if on else '끔'}")

    sp.covers_backfill_requested.connect(on_backfill)
    sp.auto_backfill_toggled.connect(on_auto_backfill)

    # 이미 아는 곡은 멜론 검색을 건너뜁니다 (곡 페이지 1번만 요청). 곡 ID는 감상 기록과 커버 색인에서 찾습니다.
    known_ids: dict[tuple[str, str], str] = {}
    for entry in reversed(persistent_stats.get("play_history", [])):  # 최근 기록이 우선
        sid = entry.get("song_id")
        if isinstance(sid, str) and sid.isdigit():
            known_ids[(entry.get("title", ""), entry.get("artist", ""))] = sid

    def lookup_song_id(display_name: str) -> str | None:
        title, artist = parse_song_info(display_name)
        return known_ids.get((title, artist)) or covers.store.song_id_for(title, artist)

    matcher.searcher.id_lookup = lookup_song_id

    def on_restore_melon() -> None:
        """트레이 '멜론 창 되돌리기': 지금 바로 되돌리고, 다시 숨기지 않도록 '멜론 창 숨기기'를 끕니다."""
        style_guard.restore_all()
        healed = style_guard.heal_orphans()
        if config_manager.hide_melon_window:
            config_manager.hide_melon_window = False
            config_manager.save_now()  # 바로 저장: 직후에 꺼져도 다음 실행에서 다시 숨기지 않게
            window.sync_controls()
        # 기록이 있는 창과 기록 없이 남은 창 모두, 아직 투명한 것이 있는지 봅니다.
        left = max(style_guard.pending_count(), style_guard.ghosted_count())
        if left:
            add_log(f"멜론 창 {left}개를 아직 되돌리지 못했어요. 잠시 뒤 다시 눌러 주세요 ('멜론 창 숨기기'는 껐어요)")
        else:
            add_log("멜론 창을 원래대로 되돌렸어요 ('멜론 창 숨기기' 끔)" + (f", 남아 있던 창 {healed}개 복구" if healed else ""))

    window.melon_restore_requested.connect(on_restore_melon)
    sp.covers_clear_requested.connect(on_clear_covers)
    refresh_covers_status()
    if recovered:
        add_log(f"이전 실행에서 남은 창 상태 {recovered}개 복구")

    applied_hwnd = None       # 고스트 모드 상태를 마지막으로 맞춘 멜론 창
    applied_mode = None
    overlay_mode = None
    last_song_title = ""
    last_lyric_text = ""
    last_save_time = time.monotonic()
    style_retry_at = 0.0
    last_text_seen = time.monotonic()
    melon_missing_since: float | None = None

    # 지금 가사 인식이 왜 되거나 안 되는지 대시보드에 보여 줍니다 (바뀔 때만 갱신).
    last_status: tuple = ()

    def set_status(level: str, title: str, detail: str = "", action: str = "") -> None:
        nonlocal last_status
        if (level, title, detail, action) == last_status:
            return
        last_status = (level, title, detail, action)
        window.dashboard_page.set_status(level, title, detail, action)
        if level != "ok":
            add_log(title)

    current_song_info = None
    cover_done_for = None  # 커버 받기를 이미 맡긴 재생 기록 (current_song_info와 같은 객체면 더 확인하지 않음)
    current_song_lines = 0
    current_song_played = 0.0   # 지금 곡을 실제로 재생한 시간 (초)
    session_played = 0.0        # 이번 실행에서 실제로 재생한 시간 (초)
    # 파일에 남기는 누적값은 '감상 기록 저장'이 켜져 있을 때 늘어난 만큼만 더합니다.
    base_total_lines = persistent_stats.get("total_lines", 0)
    recorded_played = 0.0
    recorded_lines = 0
    recording = _app_config.record_history
    last_tick = time.monotonic()

    media = MelonMediaSession()

    # 새 버전 확인 (자동: 30초 뒤·하루마다, 수동: 정보 페이지 '지금 확인')
    updater = UpdateChecker()

    def on_check_now() -> None:
        if updater.check_now():
            window.info_page.set_update_status("최신 버전을 확인하고 있어요…", checking=True)

    window.info_page.check_update_requested.connect(on_check_now)
    media_state = MediaState()
    next_media_poll = 0.0

    def start_play(song_title_str: str, repeat: bool = False, first: bool = False) -> None:
        """새 재생 한 건을 기록합니다 (곡이 바뀌었거나 같은 곡을 처음부터 다시 틀었을 때)."""
        nonlocal current_song_info, current_song_lines, current_song_played
        title, artist = parse_song_info(song_title_str)
        if first and not repeat:
            # 프로그램을 다시 켰는데(업데이트 재시작 등) 같은 곡이 이어지는 중이면 기록을 새로 만들지 않습니다.
            prev = resumable_entry(persistent_stats.get("play_history", []), title, artist, time.time())
            if prev is not None:
                current_song_info = prev
                current_song_lines = int(prev.get("lines", 0))
                current_song_played = float(prev.get("play_time_sec", 0))
                matcher.reset_recent()
                overlay.update_song_info(title, artist)
                window.set_now_playing(title, artist, prev.get("song_id"))
                add_log(f"이어서 듣는 곡: {song_title_str}")
                return
        session_stats["play_count"] += 1
        current_song_lines = 0
        current_song_played = 0.0
        matcher.reset_recent()  # 새 재생 시작 시 가사 위치 기억 초기화
        current_song_info = {
            "title": title,
            "artist": artist,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "play_time_sec": 0,
            "lines": 0,
        }
        overlay.update_song_info(title, artist)
        window.set_now_playing(title, artist)
        add_log(f"{'반복 재생' if repeat else '새로운 곡 감지'}: {song_title_str}")
        if recording:
            window.music_page.add_entry(current_song_info)
            persistent_stats["play_history"].insert(0, current_song_info)
            save_stats(persistent_stats, _app_config.data_dir)

    saved_pause_until = melon_http.paused_until_epoch()
    if saved_pause_until:
        add_log(f"지난 실행에 이어 {melon_http.pause_text()}")
    next_auto_backfill = time.monotonic() + covers.AUTO_BACKFILL_INTERVAL_SEC

    target_win = None
    next_window_scan = 0.0
    last_target_ok = False
    next_ocr_at = 0.0
    last_shown: tuple = ()
    last_stats_ui = 0.0
    capture_future = None  # 아직 끝나지 않은 캡처 (멜론이 응답하지 않을 때)
    # 가사 영역 화면이 지난번과 같으면 확대·OCR을 건너뛰고 지난 결과를 씁니다.
    # 가사는 몇 초에 한 번 바뀌므로 0.2초마다 하던 OCR 대부분이 같은 그림이었습니다 (CPU 절약).
    last_roi = None
    last_ocr_lines: list[str] = []

    async def capture_pumped(hwnd_):
        """캡처를 작업 스레드에서 돌리는 동안 화면과 단축키 처리를 계속합니다."""
        nonlocal capture_future
        if capture_future is not None and not capture_future.done():
            return None  # 지난 캡처가 아직 멈춰 있음 → 이번 회차는 건너뜀
        fut = asyncio.get_running_loop().run_in_executor(_capture_pool, capture_covered_window, hwnd_)
        capture_future = fut
        deadline = time.monotonic() + CAPTURE_TIMEOUT
        while not fut.done():
            app.processEvents()
            _drain_pending_actions()
            if not is_running or time.monotonic() > deadline:
                return None
            await asyncio.sleep(0.01)
        return fut.result()

    try:
        # 업데이트 직후라면, 메인 루프까지 정상으로 올라온 것을 확인한 뒤 임시 파일·이전 버전 백업을 지웁니다.
        if "--updated-from" in sys.argv:
            add_log(f"업데이트 완료: {sys.argv[sys.argv.index('--updated-from') + 1] if sys.argv.index('--updated-from') + 1 < len(sys.argv) else '?'} → {APP_VERSION}")
        from core.update_install import cleanup_after_update
        import threading
        threading.Thread(target=cleanup_after_update, args=(list(sys.argv),), daemon=True).start()

        while is_running:
            app.processEvents()

            _drain_pending_actions()
            if not is_running:
                break

            is_ghost_mode = config_manager.ghost_mode
            if is_ghost_mode != overlay_mode:
                overlay.set_ghost_mode(is_ghost_mode)
                overlay_mode = is_ghost_mode
            # 멜론 창은 '고스트 모드 + 멜론 창 숨기기'일 때만 투명하게 만듭니다.
            hide_melon = is_ghost_mode and config_manager.hide_melon_window

            # 멜론 프로세스의 창만 대상으로 삼습니다 (다른 프로그램 창을 건드리지 않도록).
            now = time.monotonic()
            target_win = recheck_window(target_win) if now < next_window_scan else None
            if target_win is None and now >= next_window_scan or target_win is None and last_target_ok:
                target_win = find_melon_window()
                next_window_scan = now + WINDOW_RESCAN_INTERVAL
            last_target_ok = target_win is not None

            result = updater.poll(_app_config.auto_update_check)
            if result is not None:
                kind, payload, manual = result
                if kind == "available":
                    if manual or payload.version != _app_config.skipped_version:
                        window.show_update_available(payload, manual)
                        add_log(f"새 버전 {payload.version} 있음")
                elif kind == "latest":
                    window.info_page.set_update_status(f"최신 버전을 쓰고 있어요 ({APP_VERSION})")
                    window.info_page.hide_install()
                elif manual:
                    window.info_page.set_update_status(f"확인하지 못했어요. 인터넷 연결을 확인해 주세요. ({payload[:80]})")
                else:
                    window.info_page.set_update_status(f"지금 버전: {APP_VERSION}")

            # 1분마다 자동 저장 (멜론 창이 없어도)
            if now - last_save_time >= 60:
                save_stats(persistent_stats, _app_config.data_dir)
                last_save_time = now

            # 재생 상태 (1초마다): 실제로 재생 중일 때만 감상 시간을 셉니다.
            restarted = False
            if now >= next_media_poll:
                next_media_poll = now + 1.0
                prev_state = media_state
                media_state = await media.poll()
                restarted = is_restart(prev_state, media_state, current_song_played)
                # 멜론 요청을 쉬기 시작했거나 끝났으면 저장해 둡니다 (앱을 다시 켜도 이어지도록).
                pause_until = melon_http.paused_until_epoch()
                if pause_until != saved_pause_until:
                    saved_pause_until = pause_until
                    _app_config.set_melon_pause(pause_until, melon_http.pause_reason())
                    if pause_until:
                        add_log(melon_http.pause_text())
                    refresh_covers_status()
                # 예전 기록 커버 자동 채우기: 실제로 듣는 동안에만, 정해진 간격으로 한 곡씩
                if now >= next_auto_backfill:
                    next_auto_backfill = now + covers.AUTO_BACKFILL_INTERVAL_SEC
                    if _app_config.auto_backfill and media_state.available and media_state.playing:
                        queued, _left = covers.store.backfill(
                            persistent_stats.get("play_history", []), limit=1, auto=True
                        )
                        if queued:
                            add_log("예전 기록 커버 자동 채우기: 한 곡 찾는 중")
                            refresh_covers_status()
                if covers.store.take_updated():
                    window.refresh_covers()
                    refresh_covers_status()
            dt = min(now - last_tick, 1.0)
            last_tick = now
            # 미디어 세션을 못 찾으면 예전처럼 '멜론 창이 보이면 재생 중'으로 봅니다.
            playing = media_state.playing if media_state.available else target_win is not None
            # '감상 기록 저장'을 끄면 그 순간부터 지금 곡의 저장된 기록도 더 이상 고치지 않습니다.
            now_recording = _app_config.record_history
            if recording and not now_recording and current_song_info is not None:
                current_song_info = dict(current_song_info)  # 기록 목록과 분리된 복사본으로 계속 셈
            if now_recording != recording:
                add_log("감상 기록 저장 " + ("켬 (다음 곡부터 기록)" if now_recording else "끔"))
            recording = now_recording
            if playing and current_song_info is not None:
                current_song_played += dt
                session_played += dt
                current_song_info["play_time_sec"] = int(current_song_played)
                if recording:
                    recorded_played += dt
            session_stats["session_duration"] = session_played
            persistent_stats["total_play_time_sec"] = int(session_stats["base_play_time"] + recorded_played)

            if target_win is None and applied_hwnd is not None and not hide_melon:
                # 멜론이 최소화되거나 숨겨진 상태에서 일반 모드로 바꾼 경우
                if style_guard.restore(applied_hwnd):
                    applied_hwnd, applied_mode = None, None

            if target_win is None:
                # 멜론이 사라지면 이전 가사가 계속 떠 있지 않도록 잠시 뒤 지웁니다.
                if melon_missing_since is None:
                    melon_missing_since = now
                    if is_melon_minimized():
                        set_status("warn", "멜론 창이 최소화돼 있어요",
                                   "최소화하면 가사를 읽을 수 없어요. 다른 창 뒤에 두거나 고스트 모드로 숨겨 주세요.")
                    else:
                        set_status("warn", "멜론을 찾고 있어요",
                                   "멜론 PC 플레이어를 실행하고 가사가 보이게 띄워 주세요.")
                elif now - melon_missing_since > 3 and last_lyric_text != "":
                    overlay.update_lyrics("", "")
                    window.dashboard_page.curr_lyric.setText("")
                    last_lyric_text = ""
                    last_shown = ()
            else:
                melon_missing_since = None

            if target_win:
                hwnd = target_win.hwnd

                # 대상 창이나 모드가 바뀌었으면 창 스타일 적용 (실패하면 5초 뒤 재시도)
                if (hwnd != applied_hwnd or hide_melon != applied_mode) and now >= style_retry_at:
                    ok = True
                    if applied_hwnd is not None and hwnd != applied_hwnd:
                        ok = style_guard.restore(applied_hwnd)
                    ok = style_guard.set_ghost(hwnd, hide_melon) and ok
                    if ok:
                        applied_hwnd, applied_mode = hwnd, hide_melon
                        add_log(f"멜론 창: {'숨김' if hide_melon else '표시'}")
                    else:
                        style_retry_at = now + 5.0
                        add_log("창 스타일 변경 실패 (5초 뒤 재시도)")

                # 곡 변경 감지
                current_song_title = target_win.title.replace(" - Melon", "").strip()
                # 곡이 없을 때의 창 제목('멜론 PC 플레이어' 등)은 '제목 - 가수' 형식이 아니므로 기록하지 않고,
                # '이전 곡'으로도 기억하지 않습니다. 곡이 바뀌는 순간 잠깐 이 제목이 됐다가 같은 곡으로 돌아와도
                # 같은 곡을 두 번 기록하지 않게 하려는 것입니다.
                if is_song_title(current_song_title) and current_song_title != last_song_title:
                    first_song = not last_song_title
                    last_song_title = current_song_title
                    start_play(current_song_title, first=first_song)
                elif is_song_title(current_song_title) and restarted:
                    start_play(current_song_title, repeat=True)

                # 가사를 볼 사람이 없거나 멜론이 멈춰 있으면 캡처·OCR·가사 검색을 쉽니다 (CPU·외부 요청 절약).
                # 곡 변경 감지와 감상 통계는 위에서 계속합니다.
                idle_reason = recognition_idle_reason(
                    media_available=media_state.available,
                    media_playing=media_state.playing,
                    overlay_visible=config_manager.visible or overlay.editing,
                    window_visible=window.isVisible() and not window.isMinimized(),
                )
                if idle_reason:
                    set_status("ok", idle_reason, "")
                    last_text_seen = now  # 다시 시작하자마자 '글자를 찾지 못했어요'가 뜨지 않게
                    await asyncio.sleep(0.05)
                    continue

                # 캡처 및 OCR (OCR_INTERVAL마다)
                if now < next_ocr_at:
                    await asyncio.sleep(0.05)
                    continue
                next_ocr_at = now + OCR_INTERVAL
                full_img = await capture_pumped(hwnd)
                if not is_running:
                    break
                roi = None
                if not ocr_available():
                    set_status("error", "OCR을 사용할 수 없어요", f"{OCR_STATUS}. {OCR_HELP}")
                elif full_img is None:
                    set_status("warn", "멜론 창을 캡처하지 못했어요", "잠시 후 다시 시도합니다.")
                else:
                    rx, ry, rw, rh = config_manager.roi
                    img_h, img_w = full_img.shape[:2]
                    # 창 밖으로 나간 부분은 잘라내고, 절반 이상 벗어나면 영역이 어긋난 것으로 봅니다.
                    x0, y0 = max(rx, 0), max(ry, 0)
                    x1, y1 = min(rx + rw, img_w), min(ry + rh, img_h)
                    if (x1 - x0) * (y1 - y0) < rw * rh * 0.5:
                        set_status(
                            "error", "가사 인식 영역이 멜론 창을 벗어났어요",
                            "멜론 창 크기나 화면 배율이 바뀌었을 수 있어요. 가사가 보이는 곳을 다시 지정해 주세요.",
                            "roi",
                        )
                    else:
                        roi = full_img[y0:y1, x0:x1]
                if roi is not None:
                    if roi_unchanged(last_roi, roi):
                        lines = last_ocr_lines
                    else:
                        scaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)
                        lines = await windows_native_ocr_split(scaled)
                        last_roi, last_ocr_lines = roi.copy(), lines
                    if lines:
                        last_text_seen = now
                        set_status("ok", "가사를 인식하고 있어요", "" if OCR_KOREAN else OCR_STATUS)
                    elif now - last_text_seen > 8:
                        set_status(
                            "warn", "가사 영역에서 글자를 찾지 못했어요",
                            "간주 중이거나 가사가 없는 곡일 수 있어요. 계속 이러면 "
                            "가사 인식 영역을 다시 지정해 보세요.",
                            "roi",
                        )

                    # 현재 줄·다음 줄을 함께 보정 (곡 안의 위치를 고려)
                    fixed_lines, statuses = matcher.match_lines(lines, target_win.title)
                    for status in statuses:
                        add_log(status)

                    # 가사를 찾았으면 멜론 곡 ID를 기록에 남겨, 감상 기록에서 바로 곡 페이지를 열 수 있게 합니다.
                    # 커버 주소는 곡 ID보다 늦게 오므로, 받을 때까지 계속 확인합니다 (멜론 요청이 늘지는 않음).
                    if current_song_info is not None and cover_done_for is not current_song_info:
                        id_added, cover = link_song(current_song_info, matcher.searcher, target_win.title)
                        if id_added:
                            known_ids[(current_song_info["title"], current_song_info["artist"])] = current_song_info["song_id"]
                            window.set_now_playing(
                                current_song_info["title"], current_song_info["artist"], current_song_info["song_id"]
                            )
                        if cover:
                            covers.store.remember(
                                current_song_info["title"], current_song_info["artist"],
                                current_song_info["song_id"], cover,
                            )
                            # 커버 받기가 꺼져 있었다면 맡기지 못했으니, 켜면 다시 시도하도록 둡니다.
                            cover_done_for = current_song_info if covers.store.enabled else None

                    curr = fixed_lines[0] if len(fixed_lines) > 0 else "..."
                    nxt = fixed_lines[1] if len(fixed_lines) > 1 else ""

                    if curr != "..." and curr != last_lyric_text:
                        session_stats["session_lines"] += 1
                        last_lyric_text = curr
                        if recording:
                            recorded_lines += 1
                            persistent_stats["total_lines"] = base_total_lines + recorded_lines
                        
                        if current_song_info is not None:
                            current_song_lines += 1
                            current_song_info["lines"] = current_song_lines


                    # 화면과 터미널은 가사가 바뀔 때만 갱신합니다.
                    if (curr, nxt) != last_shown:
                        last_shown = (curr, nxt)
                        overlay.update_lyrics(curr, nxt)
                        window.dashboard_page.curr_lyric.setText(curr)
                        # 가사 문장은 파일에 남기지 않으므로, 이 화면 출력은 진단 로그를 거치지 않습니다.
                        mode_status = "👻 게임 모드" if is_ghost_mode else "🖱️  조작 모드"
                        app_log.console("\033[H\033[J")
                        app_log.console(f"상태: {mode_status} | 대상: {target_win.title}")
                        app_log.console("-" * 40)
                        app_log.console(f"🔥 현재: {curr}")
                        app_log.console(f"💤 다음: {nxt}")
                        app_log.console("-" * 40)
                        app_log.console("[ 시스템 로그 ]")
                        for log in log_history:
                            app_log.console(f" > {log}")

                    # 통계 카드는 1초에 한 번이면 충분합니다.
                    if now - last_stats_ui >= 1.0:
                        last_stats_ui = now
                        window.dashboard_page.update_stats(session_stats, persistent_stats.get("play_history", []))

                    QApplication.processEvents()

            await asyncio.sleep(0.05)

    finally:
        # 멜론 창 복구를 가장 먼저 합니다. 뒤의 정리 단계가 실패해도 창은 원래대로 돌아와야 합니다.
        try:
            print("\n[🧹] 멜론 창 상태 원복 중...")
            style_guard.restore_all()
        except Exception as e:
            print(f"[⚠️] 멜론 창 상태 원복 실패: {e}")
        hotkey_mgr.unhook_all()
        if window.tray is not None:
            window.tray.hide()
        config_manager.save_now()
        # 멜론 요청을 쉬는 중이면 그 상태를 남깁니다 (1초마다 저장하지만, 그 사이에 꺼질 수 있으므로).
        _app_config.set_melon_pause(melon_http.paused_until_epoch(), melon_http.pause_reason())
        if _app_config:
            save_stats(persistent_stats, _app_config.data_dir)
        matcher.searcher.shutdown()
        covers.store.shutdown()
        updater.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        # 빌드 확인용 자체 점검 (build.ps1이 실행). 실제 설정·데이터·멜론은 건드리지 않습니다.
        from core.smoke_test import run as run_smoke_test
        sys.exit(run_smoke_test(sys.argv))
    if "--apply-update" in sys.argv:
        # 업데이트로 받은 새 exe가 '적용 모드'로 실행된 경우: 화면 없이 교체만 하고 끝냅니다.
        from core.update_install import run_apply_mode
        sys.exit(run_apply_mode(sys.argv))
    asyncio.run(main())
