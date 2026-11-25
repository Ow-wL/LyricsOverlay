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

import cv2
from PySide6.QtWidgets import QApplication  # type: ignore

from core.hotkey_manager import HotkeyManager
from core.ocr_engine import OCR_HELP, OCR_KOREAN, OCR_STATUS, ocr_available, windows_native_ocr_split
from core.stats_manager import load_stats, make_session_stats, parse_song_info, save_stats
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

    # 지난번 강제 종료로 투명하게 남은 멜론 창이 있으면 가장 먼저 복구합니다.
    # (이후 단계에서 무엇이 실패해도 멜론 창은 원래대로 돌아오게)
    style_guard = WindowStyleGuard(_app_config.data_dir)
    recovered = style_guard.recover_from_file()

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

    window.show()

    overlay = window.overlay
    config_manager = window.config_manager
    matcher = LyricMatcher()

    # 단축키 매니저
    hotkey_mgr = HotkeyManager(
        on_ghost_toggle=lambda: _pending_actions.put(_on_toggle_mode),
        on_quit=lambda: _pending_actions.put(_on_quit),
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
    media_labels = {"prev": "이전 곡", "play_pause": "재생/일시정지", "next": "다음 곡"}
    def on_media_action(key: str) -> None:
        add_log(f"미디어 제어: {media_labels.get(key, key)}")
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
    _app_config.add_listener(style_guard.set_data_dir)
    _app_config.add_listener(on_data_dir_changed)
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

    def start_play(song_title_str: str, repeat: bool = False) -> None:
        """새 재생 한 건을 기록합니다 (곡이 바뀌었거나 같은 곡을 처음부터 다시 틀었을 때)."""
        nonlocal current_song_info, current_song_lines, current_song_played
        session_stats["play_count"] += 1
        title, artist = parse_song_info(song_title_str)
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
        window.dashboard_page.set_now_playing(title, artist)
        add_log(f"{'반복 재생' if repeat else '새로운 곡 감지'}: {song_title_str}")
        if recording:
            window.music_page.add_entry(current_song_info)
            persistent_stats["play_history"].insert(0, current_song_info)
            save_stats(persistent_stats, _app_config.data_dir)

    target_win = None
    next_window_scan = 0.0
    last_target_ok = False
    next_ocr_at = 0.0
    last_shown: tuple = ()
    last_stats_ui = 0.0
    capture_future = None  # 아직 끝나지 않은 캡처 (멜론이 응답하지 않을 때)

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
                if current_song_title != last_song_title:
                    last_song_title = current_song_title
                    if current_song_title:
                        start_play(current_song_title)
                elif current_song_title and restarted:
                    start_play(current_song_title, repeat=True)

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
                    scaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)

                    lines = await windows_native_ocr_split(scaled)
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
                        print("\033[H\033[J")
                        mode_status = "👻 게임 모드" if is_ghost_mode else "🖱️  조작 모드"
                        print(f"상태: {mode_status} | 대상: {target_win.title}")
                        print("-" * 40)
                        print(f"🔥 현재: {curr}")
                        print(f"💤 다음: {nxt}")
                        print("-" * 40)
                        print("[ 시스템 로그 ]")
                        for log in log_history:
                            print(f" > {log}")

                    # 통계 카드는 1초에 한 번이면 충분합니다.
                    if now - last_stats_ui >= 1.0:
                        last_stats_ui = now
                        window.dashboard_page.update_stats(session_stats, persistent_stats.get("play_history", []))

                    QApplication.processEvents()

            await asyncio.sleep(0.05)

    finally:
        hotkey_mgr.unhook_all()
        if window.tray is not None:
            window.tray.hide()
        config_manager.save_now()
        print("\n[🧹] 멜론 창 상태 원복 중...")
        style_guard.restore_all()
        if _app_config:
            save_stats(persistent_stats, _app_config.data_dir)
        matcher.searcher.shutdown()
        updater.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    if "--apply-update" in sys.argv:
        # 업데이트로 받은 새 exe가 '적용 모드'로 실행된 경우: 화면 없이 교체만 하고 끝냅니다.
        from core.update_install import run_apply_mode
        sys.exit(run_apply_mode(sys.argv))
    asyncio.run(main())
